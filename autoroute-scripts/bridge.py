"""Tie isolated GND pour islands back to the main ground with a small 2-layer grid A* router."""
import heapq, math, sys
import pcbnew
from geom import Space, mm, _dist_pt_seg

SRC, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(SRC)
gnd = b.GetNetcodeFromNetname('GND')
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
HW, CLR, VIA_R, GRID = mm(0.15), mm(0.15), mm(0.3), mm(0.1)
filler = pcbnew.ZONE_FILLER(b)


def zones():
    return {z.GetLayer(): z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gnd}


def groups():
    """Union-find over pour pieces, joined by GND vias and GND PTH pads."""
    zs = zones()
    fill = {L: zs[L].GetFilledPolysList(L) for L in LAYERS}
    pieces = {L: [fill[L].UnitSet(k) for k in range(fill[L].OutlineCount())] for L in LAYERS}
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            a = parent[a]
        return a
    joins = [t.GetPosition() for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetCode() == gnd]
    joins += [p.GetPosition() for f in b.GetFootprints() for p in f.Pads()
              if p.GetNetCode() == gnd and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    for pos in joins:
        hit = [(L, k) for L in LAYERS for k, pc in enumerate(pieces[L]) if pc.Contains(pos)]
        for h in hit[1:]:
            parent[find(hit[0])] = find(h)
    out = {}
    for L in LAYERS:
        for k in range(len(pieces[L])):
            out.setdefault(find((L, k)), []).append((L, k))
    return pieces, list(out.values())


def route(sp, src_pts, goal, window):
    """A* from any (x, y, L) in src_pts to a node where goal(x, y, L) is true."""
    x0, y0, x1, y1 = window
    pads = [(polys, n) for p, n, polys, f in sp.pads if n != gnd]
    tracks = [t for t in sp.tracks if t[6] != gnd]
    vias = [v for v in sp.vias if v[3] != gnd]
    kos = [z for z in sp.keepouts if z.GetDoNotAllowTracks()]
    memo = {}

    def free(i, j, L, r=HW):
        key = (i, j, L, r)
        if key in memo:
            return memo[key]
        x, y = x0 + i * GRID, y0 + j * GRID
        v = pcbnew.VECTOR2I(int(x), int(y))
        ok = sp.edge.Contains(v) and sp.edge.Outline(0).SquaredDistance(v, True) >= (r + mm(0.3)) ** 2
        ok = ok and not any(z.IsOnLayer(L) and z.Outline().Collide(v, int(r)) for z in kos)
        ok = ok and not any(L in polys and polys[L].Collide(v, int(r + CLR)) for polys, n in pads)
        ok = ok and not any(tl == L and _dist_pt_seg(x, y, ax, ay, bx, by) < thw + r + CLR
                            for ax, ay, bx, by, thw, tl, tn in tracks)
        ok = ok and not any(math.hypot(vx - x, vy - y) < vr + r + CLR for vx, vy, vr, vn in vias)
        memo[key] = ok
        return ok

    W, H = int((x1 - x0) / GRID), int((y1 - y0) / GRID)
    start = []
    for sx, sy, L in src_pts:
        i, j = round((sx - x0) / GRID), round((sy - y0) / GRID)
        start.append((i, j, L))
    openq = [(0, 0, s, None) for s in start]
    seen = {}
    while openq:
        f_, g, node, prev = heapq.heappop(openq)
        if node in seen:
            continue
        seen[node] = prev
        i, j, L = node
        x, y = x0 + i * GRID, y0 + j * GRID
        if prev is not None and goal(x, y, L):
            path = [node]
            while seen[path[-1]] is not None:
                path.append(seen[path[-1]])
            return [(x0 + a * GRID, y0 + c * GRID, l) for a, c, l in reversed(path)]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < W and 0 <= nj < H and (ni, nj, L) not in seen and free(ni, nj, L):
                heapq.heappush(openq, (g + math.hypot(di, dj), g + math.hypot(di, dj), (ni, nj, L), node))
        other = LAYERS[1] if L == LAYERS[0] else LAYERS[0]
        if (i, j, other) not in seen and free(i, j, L, VIA_R) and free(i, j, other, VIA_R):
            heapq.heappush(openq, (g + 25, g + 25, (i, j, other), node))
    return None


for attempt in range(6):
    filler.Fill(b.Zones())
    pieces, grps = groups()
    grps.sort(key=lambda g: -sum(pieces[L][k].Area() for L, k in g))
    if len(grps) == 1:
        print('GND pours fully connected')
        break
    main = grps[0]
    island = grps[1]
    sp = Space(b)
    # start from GND pads / vias / interior points of the island
    src = []
    for L, k in island:
        pc = pieces[L][k]
        for p, n, polys, f in sp.pads:
            if n == gnd and L in polys and pc.Contains(p.GetPosition()):
                src.append((p.GetPosition().x, p.GetPosition().y, L))
        if not src:
            c = pc.BBox().Centre()
            src.append((c.x, c.y, L))
    main_polys = [(L, pieces[L][k]) for L, k in main]

    def goal(x, y, L):
        v = pcbnew.VECTOR2I(int(x), int(y))
        return any(ML == L and pc.Contains(v) and pc.Outline(0).SquaredDistance(v, True) > mm(0.35) ** 2
                   for ML, pc in main_polys)

    cx = sum(s[0] for s in src) / len(src)
    cy = sum(s[1] for s in src) / len(src)
    R = mm(11)
    path = route(sp, src, goal, (cx - R, cy - R, cx + R, cy + R))
    if not path:
        print('could not bridge island', island)
        break
    # emit: merge collinear runs per layer, vias at layer changes
    segs, vias_at = [], []
    run = [path[0]]
    for a, c in zip(path, path[1:]):
        if a[2] != c[2]:
            segs.append(run)
            vias_at.append((a[0], a[1]))
            run = [c]
        else:
            run.append(c)
    segs.append(run)
    for run in segs:
        pts = [run[0]]
        for k in range(1, len(run) - 1):
            ax, ay, _ = pts[-1]
            bx, by, _ = run[k]
            cx_, cy_, _ = run[k + 1]
            if abs((bx - ax) * (cy_ - by) - (by - ay) * (cx_ - bx)) > 1:
                pts.append(run[k])
        pts.append(run[-1])
        for (ax, ay, L), (bx, by, _) in zip(pts, pts[1:]):
            if (ax, ay) == (bx, by):
                continue
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(int(ax), int(ay)))
            t.SetEnd(pcbnew.VECTOR2I(int(bx), int(by)))
            t.SetWidth(2 * HW); t.SetLayer(L); t.SetNetCode(gnd)
            b.Add(t)
    for vx, vy in vias_at:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(vx), int(vy)))
        v.SetWidth(2 * VIA_R); v.SetDrill(mm(0.3)); v.SetNetCode(gnd)
        b.Add(v)
    print('bridged island', island, 'with', len(path), 'steps,', len(vias_at), 'vias')

filler.Fill(b.Zones())
pcbnew.SaveBoard(OUT, b)
