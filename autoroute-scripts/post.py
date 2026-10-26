"""Post-route: widen power where it fits, pour GND on both layers, stitch, fill."""
import math, sys
import pcbnew
from geom import Space, mm, _dist_pt_seg, fanout_gnd

SRC, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(SRC)
CLR = mm(0.2)   # widened power keeps the roomier 0.2 mm

# board was routed at 0.15 mm (fine for any 2-layer fab); make the rules say so
ns = b.GetDesignSettings().m_NetSettings
ns.GetDefaultNetclass().SetClearance(mm(0.15))
for name, nc in ns.GetNetclasses().items():
    nc.SetClearance(mm(0.15))
ns.RecomputeEffectiveNetclasses()


def seg_fits(sp, t, hw):
    s, e = t.GetStart(), t.GetEnd()
    ax, ay, bx, by = s.x, s.y, e.x, e.y
    L, net = t.GetLayer(), t.GetNetCode()
    n = max(2, int(math.hypot(bx - ax, by - ay) / mm(0.05)))
    for i in range(n + 1):
        x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
        v = pcbnew.VECTOR2I(int(x), int(y))
        if sp.edge.Outline(0).SquaredDistance(v, True) < (hw + mm(0.3)) ** 2:
            return False
        for z in sp.keepouts:
            if z.GetDoNotAllowTracks() and z.IsOnLayer(L) and z.Outline().Collide(v, int(hw)):
                return False
        for p, pn, polys, f in sp.pads:
            if pn == net or L not in polys:
                continue
            if polys[L].Collide(v, int(hw + CLR)):
                return False
        for vx, vy, vr, vn in sp.vias:
            if vn != net and math.hypot(vx - x, vy - y) < vr + hw + CLR:
                return False
        for tx, ty, ux, uy, thw, tl, tn in sp.tracks:
            if tl == L and tn != net and _dist_pt_seg(x, y, tx, ty, ux, uy) < thw + hw + CLR:
                return False
    return True


# ---- tented GND vias are fine under the module; then fan out GND pads that still have no via
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetZoneName() == 'under-module':
        z.SetDoNotAllowVias(False)
print('late fanout', fanout_gnd(b, Space(b), only_bare=True))

# ---- widen power, biggest first
sp = Space(b)
targets = {'VBUS': (0.8, 0.6, 0.5), '+5V': (0.8, 0.6, 0.5), '+3V3': (0.6, 0.5)}
stats = {}
for netname, widths in targets.items():
    code = b.GetNetcodeFromNetname(netname)
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_TRACK' or t.GetNetCode() != code:
            continue
        for w in widths:
            if mm(w) <= t.GetWidth():
                break
            if seg_fits(sp, t, mm(w) / 2):
                old = t.GetWidth()
                t.SetWidth(mm(w))
                s, e = t.GetStart(), t.GetEnd()
                for i, tr in enumerate(sp.tracks):
                    if tr[:4] == (s.x, s.y, e.x, e.y) and tr[5] == t.GetLayer():
                        sp.tracks[i] = (s.x, s.y, e.x, e.y, mm(w) / 2, t.GetLayer(), t.GetNetCode())
                        break
                stats.setdefault(netname, {}).setdefault(w, 0)
                stats[netname][w] += 1
                break
print('widened', stats)

# ---- GND pours on both layers
gnd = b.GetNetcodeFromNetname('GND')
edge = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(edge, True)
for L in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b)
    z.SetLayer(L)
    z.SetNetCode(gnd)
    z.SetZoneName('GND')
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    o = edge.Outline(0)
    for i in range(o.PointCount()):
        ol.Append(o.CPoint(i))
    b.Add(z)

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())

# ---- stitching vias on a grid wherever both pours exist
sp = Space(b)
zones = {z.GetLayer(): z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gnd}
bb = edge.BBox()
STEP, VD, SPACING = mm(1.0), mm(0.6), mm(2.4)
added = []
y = bb.GetTop() + STEP // 2
while y < bb.GetBottom():
    x = bb.GetLeft() + STEP // 2
    while x < bb.GetRight():
        v = pcbnew.VECTOR2I(int(x), int(y))
        inside = all(zones[L].GetFilledPolysList(L).Contains(v) for L in zones)
        near = any(n == gnd and math.hypot(vx - x, vy - y) < SPACING for vx, vy, vr, n in sp.vias)
        if inside and not near and sp.via_ok(x, y, VD / 2, gnd, mm(0.25), allow_courtyard=False):
            # the pour around the via must be a real area, not a sliver
            ring_ok = True
            for L in zones:
                fp = zones[L].GetFilledPolysList(L)
                for k in range(8):
                    a = k * math.pi / 4
                    q = pcbnew.VECTOR2I(int(x + mm(0.55) * math.cos(a)), int(y + mm(0.55) * math.sin(a)))
                    if not fp.Contains(q):
                        ring_ok = False
            if ring_ok:
                via = pcbnew.PCB_VIA(b)
                via.SetPosition(v)
                via.SetWidth(VD); via.SetDrill(mm(0.3)); via.SetNetCode(gnd)
                b.Add(via)
                sp.add_via(x, y, VD / 2, gnd)
                added.append(via)
        x += STEP
    y += STEP
print('stitching vias', len(added))
filler.Fill(b.Zones())


# ---- make sure every front pour piece is tied to every back piece it overlaps
def ring_in(fp, x, y, r):
    return fp.Contains(pcbnew.VECTOR2I(int(x), int(y))) and all(
        fp.Contains(pcbnew.VECTOR2I(int(x + r * math.cos(k * math.pi / 4)), int(y + r * math.sin(k * math.pi / 4))))
        for k in range(8))


sp = Space(b)
bridged = 0
fF = zones[pcbnew.F_Cu].GetFilledPolysList(pcbnew.F_Cu)
fB = zones[pcbnew.B_Cu].GetFilledPolysList(pcbnew.B_Cu)
for i in range(fF.OutlineCount()):
    for j in range(fB.OutlineCount()):
        pi, pj = fF.UnitSet(i), fB.UnitSet(j)
        both = pcbnew.SHAPE_POLY_SET(pi)
        both.BooleanIntersection(pj)
        if both.OutlineCount() == 0:
            continue
        if any(n == gnd and both.Contains(pcbnew.VECTOR2I(int(vx), int(vy))) for vx, vy, vr, n in sp.vias):
            continue
        ib = both.BBox()
        found = None
        yy = ib.GetTop()
        while yy <= ib.GetBottom() and not found:
            xx = ib.GetLeft()
            while xx <= ib.GetRight():
                if ring_in(pi, xx, yy, mm(0.55)) and ring_in(pj, xx, yy, mm(0.55)) \
                        and sp.via_ok(xx, yy, VD / 2, gnd, mm(0.25), allow_courtyard=True):
                    found = (xx, yy)
                    break
                xx += mm(0.15)
            yy += mm(0.15)
        if found:
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pcbnew.VECTOR2I(int(found[0]), int(found[1])))
            via.SetWidth(VD); via.SetDrill(mm(0.3)); via.SetNetCode(gnd)
            b.Add(via)
            sp.add_via(found[0], found[1], VD / 2, gnd)
            bridged += 1
print('bridge vias', bridged, 'pieces F/B', fF.OutlineCount(), fB.OutlineCount())
filler.Fill(b.Zones())
pcbnew.SaveBoard(OUT, b)
