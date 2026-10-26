"""Pre-route: keep tracks out from under the module on B.Cu and give every GND pad its own via."""
import math, sys
import pcbnew
from geom import Space, mm, fanout_gnd

SRC, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(SRC)

# ---- B.Cu: no tracks/vias under the ESP32 body (between its pad rows), pour still allowed
u3 = b.FindFootprintByReference('U3')
c = u3.GetPosition()
ko = pcbnew.ZONE(b)
ko.SetIsRuleArea(True)
ko.SetDoNotAllowTracks(True)
ko.SetDoNotAllowVias(False)   # tented GND vias under the module are fine
ko.SetDoNotAllowZoneFills(False)
ko.SetDoNotAllowPads(False)
ko.SetDoNotAllowFootprints(False)
ko.SetLayer(pcbnew.B_Cu)
ko.SetZoneName('under-module')
ol = ko.Outline()
ol.NewOutline()
# module body is y -13.15..6.95 (antenna up); pad rows at x = +-8.75
for dx, dy in [(-7.6, -7.0), (7.6, -7.0), (7.6, 7.3), (-7.6, 7.3)]:
    ol.Append(c.x + mm(dx), c.y + mm(dy))
b.Add(ko)

# ---- GND fanout
placed, missed = fanout_gnd(b, Space(b))
pcbnew.SaveBoard(OUT, b)
print('fanout vias', placed, 'missed', missed)
