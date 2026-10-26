"""Small clearance checker used to drop GND fanout and stitching vias into free space."""
import math
import pcbnew

mm = pcbnew.FromMM
ERR = mm(0.005)


def _poly(item, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, 0, ERR, pcbnew.ERROR_INSIDE)
    return ps


def _dist_pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Space:
    def __init__(self, board):
        self.b = board
        self.pads = []      # (pad, netcode, {layer: poly}, footprint)
        for f in board.GetFootprints():
            for p in f.Pads():
                polys = {}
                for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if p.IsOnLayer(L):
                        polys[L] = _poly(p, L)
                self.pads.append((p, p.GetNetCode(), polys, f))
        self.courtyards = []
        for f in board.GetFootprints():
            for L in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                cy = f.GetCourtyard(L)
                if cy.OutlineCount():
                    self.courtyards.append((f, cy))
        self.keepouts = []
        for z in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
            if z.GetIsRuleArea():
                self.keepouts.append(z)
        self.edge = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(self.edge, True)
        self.vias = []      # (x, y, r)
        self.tracks = []    # (ax, ay, bx, by, halfwidth, layer, netcode)
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                self.vias.append((p.x, p.y, t.GetWidth(pcbnew.F_Cu) / 2, t.GetNetCode()))
            else:
                s, e = t.GetStart(), t.GetEnd()
                self.tracks.append((s.x, s.y, e.x, e.y, t.GetWidth() / 2, t.GetLayer(), t.GetNetCode()))

    def via_ok(self, x, y, r, net, clr, own_fp=None, allow_courtyard=False):
        v = pcbnew.VECTOR2I(int(x), int(y))
        # inside board with edge margin
        if not self.edge.Contains(v) or self.edge.Outline(0).SquaredDistance(v, True) < (r + mm(0.4)) ** 2:
            return False
        for z in self.keepouts:
            if z.GetDoNotAllowVias() and z.Outline().Collide(v, int(r)):
                return False
        for p, n, polys, f in self.pads:
            gap = r + (mm(0.15) if n == net else clr)
            for ps in polys.values():
                if ps.Collide(v, int(gap)):
                    return False
        if not allow_courtyard:
            for f, cy in self.courtyards:
                if f is own_fp or f.GetReference() == 'U3':
                    continue  # module: B.Cu keepout + pad clearance already cover it
                if cy.Collide(v, int(r)):
                    return False
        for vx, vy, vr, n in self.vias:
            if math.hypot(vx - x, vy - y) < vr + r + clr:
                return False
        for ax, ay, bx, by, hw, L, n in self.tracks:
            if n == net:
                continue
            if _dist_pt_seg(x, y, ax, ay, bx, by) < hw + r + clr:
                return False
        return True

    def stub_ok(self, ax, ay, bx, by, hw, layer, net, clr, own_pad):
        n = max(2, int(math.hypot(bx - ax, by - ay) / mm(0.08)))
        for i in range(n + 1):
            x = ax + (bx - ax) * i / n
            y = ay + (by - ay) * i / n
            v = pcbnew.VECTOR2I(int(x), int(y))
            for p, pn, polys, f in self.pads:
                if p is own_pad or pn == net or layer not in polys:
                    continue
                if polys[layer].Collide(v, int(hw + clr)):
                    return False
            for tx, ty, ux, uy, thw, L, tn in self.tracks:
                if L == layer and tn != net and _dist_pt_seg(x, y, tx, ty, ux, uy) < thw + hw + clr:
                    return False
        return True

    def add_via(self, x, y, r, net):
        self.vias.append((x, y, r, net))

    def add_track(self, ax, ay, bx, by, hw, layer, net):
        self.tracks.append((ax, ay, bx, by, hw, layer, net))


def fanout_gnd(b, sp, only_bare=False):
    """Give each GND SMD pad a short stub + via. only_bare: skip pads that already have a GND track."""
    gnd = b.GetNetcodeFromNetname('GND')
    VIA_D, DRILL, STUB_W, CLR = mm(0.6), mm(0.3), mm(0.4), mm(0.2)
    starts = set()
    if only_bare:
        for t in b.GetTracks():
            if t.GetNetCode() == gnd and t.GetClass() == 'PCB_TRACK':
                starts.add((t.GetStart().x, t.GetStart().y))
                starts.add((t.GetEnd().x, t.GetEnd().y))
    placed, missed = 0, []
    for f in b.GetFootprints():
        ref = f.GetReference()
        for p in f.Pads():
            if p.GetNetCode() != gnd or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if ref == 'U3' and p.GetNumber() == '19':
                continue  # exposed pad already has thermal vias
            px, py = p.GetPosition().x, p.GetPosition().y
            if (px, py) in starts:
                continue
            layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            done = False
            for d in (0.9, 1.05, 1.2, 1.4, 1.6, 1.9, 2.2, 2.6, 3.0):
                for k in range(24):
                    a = 2 * math.pi * k / 24
                    x, y = px + mm(d) * math.cos(a), py + mm(d) * math.sin(a)
                    if not sp.via_ok(x, y, VIA_D / 2, gnd, CLR, own_fp=f):
                        continue
                    if not sp.stub_ok(px, py, x, y, STUB_W / 2, layer, gnd, CLR, p):
                        continue
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                    v.SetWidth(VIA_D); v.SetDrill(DRILL); v.SetNetCode(gnd)
                    b.Add(v)
                    t = pcbnew.PCB_TRACK(b)
                    t.SetStart(p.GetPosition()); t.SetEnd(pcbnew.VECTOR2I(int(x), int(y)))
                    t.SetWidth(STUB_W); t.SetLayer(layer); t.SetNetCode(gnd)
                    b.Add(t)
                    sp.add_via(x, y, VIA_D / 2, gnd)
                    sp.add_track(px, py, x, y, STUB_W / 2, layer, gnd)
                    placed += 1
                    done = True
                    break
                if done:
                    break
            if not done:
                missed.append(f'{ref}-{p.GetNumber()}')
    return placed, missed
