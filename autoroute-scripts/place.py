import math, sys
import pcbnew

SRC, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(SRC)
mm = pcbnew.FromMM
CX, CY = 150.0, 100.0


def P(x, y):  # star-local coords, y up -> KiCad
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY - y))


# ---------------- outline: rounded 5-point star with a flat bottom for USB-C
R, r = 26.0, 15.6
FLAT_Y = -18.0
pts = []
for i in range(10):
    a = math.radians(90 + 36 * i)
    rad = R if i % 2 == 0 else r
    pts.append((rad * math.cos(a), rad * math.sin(a)))

poly = pcbnew.SHAPE_POLY_SET()
poly.NewOutline()
for x, y in pts:
    poly.Append(P(x, y))
flat = pcbnew.SHAPE_POLY_SET()
flat.NewOutline()
for x, y in [(-8, FLAT_Y), (8, FLAT_Y), (8, -15), (-8, -15)]:
    flat.Append(P(x, y))
# only fill the bottom notch, never extend the arms
clip = pcbnew.SHAPE_POLY_SET()
clip.NewOutline()
for x, y in [(-7.2, FLAT_Y), (7.2, FLAT_Y), (7.2, 0), (-7.2, 0)]:
    clip.Append(P(x, y))
flat.BooleanIntersection(clip)
poly.BooleanAdd(flat)

err = mm(0.005)
S = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS
TIP, NOTCH = mm(3.2), mm(4.0)
poly.Inflate(-TIP, S, err)      # round convex tips
poly.Inflate(TIP, S, err)
poly.Inflate(NOTCH, S, err)     # round concave notches
poly.Inflate(-NOTCH, S, err)
poly.Simplify()

for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)
outline = poly.Outline(0)
n = outline.PointCount()
for i in range(n):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(outline.CPoint(i))
    s.SetEnd(outline.CPoint((i + 1) % n))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.05))
    b.Add(s)

# ---------------- placement: (ref, x, y, rot, side)
F, B = 'F', 'B'
place = [
    ('U3', 0.0, -1.65, 0, B),
    ('J1', 0.0, FLAT_Y + 3.7, 0, F),
]

# LEDs on the front; chain D1..D10 runs right arm -> bottom-right -> centre -> bottom-left -> left arm
LEDS = [
    (13.0, 2.2),      # D1 right inner
    (19.6, 4.8),      # D2 right tip
    (11.3, -15.6),    # D3 bottom-right tip
    (7.5, -10.2),     # D4 bottom-right inner
    (4.5, 1.5),       # D5 centre right
    (-4.5, 1.5),      # D6 centre left
    (-7.5, -10.2),    # D7 bottom-left inner
    (-11.3, -15.6),   # D8 bottom-left tip
    (-19.6, 4.8),     # D9 left tip
    (-13.0, 2.2),     # D10 left inner
]
LED_SRC = (16.6, 6.9)   # R7 feeds D1
LED_CAPS = ['C5', 'C6', 'C7', 'C8', 'C9', 'C10', 'C11', 'C12', 'C13', 'C14']
for i, (x, y) in enumerate(LEDS):
    px, py = LEDS[i - 1] if i else LED_SRC
    nx, ny = LEDS[i + 1] if i + 1 < len(LEDS) else (2 * x - px, 2 * y - py)
    # DIN (pad 3) faces the previous LED, DOUT (pad 1) faces the next
    rot = math.degrees(math.atan2(-(ny - py), -(nx - px)))
    place.append((f'D{i+1}', x, y, rot, F))

place += [
    # back, bottom strip behind the USB-C
    ('F1', 0.0, -13.3, 0, B),
    ('C1', 0.0, -10.3, 0, B),
    ('R1', -1.6, -16.9, 0, B),
    ('R2', 1.6, -16.9, 0, B),
    # back, buttons in the bottom arms
    ('SW1', 10.4, -14.0, -54, B),
    ('SW2', -10.4, -14.0, 54, B),
    # back, right side: module support parts + LED level shifter
    ('U4', 17.8, 3.6, 18, B),
    ('R7', 16.6, 6.9, 18, B),
    ('C15', 15.0, 2.9, -72, B),
    ('C3', 11.5, 4.4, 0, B),
    ('R3', 11.5, 2.6, 0, B),
    ('C4', 11.5, 0.8, 0, B),
    ('R4', 11.5, -4.6, 0, B),
    ('R5', 11.5, -6.4, 0, B),
    # back, left side: USB ESD, IO2 strap, 3V3 regulator
    ('U1', -12.4, -3.4, 90, B),
    ('R6', -11.5, 2.6, 0, B),
    ('U2', -15.6, 1.6, 0, B),
    ('C2', -19.6, 5.0, -18, B),
]

for ref, x, y, rot, side in place:
    f = b.FindFootprintByReference(ref)
    if f.IsFlipped() != (side == B):
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetPosition(P(x, y))
    f.SetOrientationDegrees(rot + (180 if side == B else 0))
    # tidy silkscreen: hide values, small refs
    f.Value().SetVisible(False)
    rf = f.Reference()
    rf.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
    rf.SetTextThickness(mm(0.1))


def pad(f, num):
    return next(p for p in f.Pads() if p.GetNumber() == num).GetPosition()


# strap/decoupling parts beside the module: put the pad that talks to the module on the module side
u3c = b.FindFootprintByReference('U3').GetPosition()
for ref, num in [('R3', '2'), ('R4', '2'), ('R5', '2'), ('R6', '2'), ('C3', '1'), ('C4', '1')]:
    f = b.FindFootprintByReference(ref)
    if abs(pad(f, num).x - u3c.x) > abs(f.GetPosition().x - u3c.x):
        f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)

# each LED's 100n sits on its VDD/DOUT side, off the data path, pad 1 (+5V) next to VDD
for i, cref in enumerate(LED_CAPS):
    d = b.FindFootprintByReference(f'D{i+1}')
    c = b.FindFootprintByReference(cref)
    if c.IsFlipped():
        c.Flip(c.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    vdd, din = pad(d, '4'), pad(d, '3')
    ux, uy = vdd.x - din.x, vdd.y - din.y
    L = math.hypot(ux, uy)
    c.SetPosition(pcbnew.VECTOR2I(int(d.GetPosition().x + mm(2.3) * ux / L), int(d.GetPosition().y + mm(2.3) * uy / L)))
    best = None
    for r in (d.GetOrientationDegrees(), d.GetOrientationDegrees() + 180):
        c.SetOrientationDegrees(r)
        p1 = pad(c, '1')
        dist = math.hypot(p1.x - vdd.x, p1.y - vdd.y)
        if best is None or dist < best[0]:
            best = (dist, r)
    c.SetOrientationDegrees(best[1])
    c.Value().SetVisible(False)
    c.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
    c.Reference().SetTextThickness(mm(0.1))

# ---------------- net classes
ds = b.GetDesignSettings()
ns = ds.m_NetSettings
dflt = ns.GetDefaultNetclass()
ds.m_MinThroughDrill = mm(0.2)
ds.m_CopperEdgeClearance = mm(0.3)
ds.m_TrackMinWidth = mm(0.15)
dflt.SetTrackWidth(mm(0.25)); dflt.SetClearance(mm(0.2))
dflt.SetViaDiameter(mm(0.6)); dflt.SetViaDrill(mm(0.3))


def mk(name, w, via, drill, clr=0.2):
    nc = pcbnew.NETCLASS(name)
    nc.SetTrackWidth(mm(w)); nc.SetClearance(mm(clr))
    nc.SetViaDiameter(mm(via)); nc.SetViaDrill(mm(drill))
    ns.SetNetclass(name, nc)


mk('Power', 0.6, 0.8, 0.4)
mk('3V3', 0.5, 0.8, 0.4)
mk('GND', 0.5, 0.8, 0.4)
mk('USB', 0.2, 0.6, 0.3, 0.15)
mk('VBUS', 0.5, 0.8, 0.4, 0.15)
for net, cls in [('VBUS', 'VBUS'), ('+5V', 'Power'), ('+3V3', '3V3'), ('GND', 'GND'),
                 ('/USB_DP', 'USB'), ('/USB_DN', 'USB')]:
    ns.SetNetclassPatternAssignment(net, cls)
ns.RecomputeEffectiveNetclasses()
b.SynchronizeNetsAndNetClasses(True)

pcbnew.SaveBoard(OUT, b)
print('saved', OUT, 'outline pts', n)
