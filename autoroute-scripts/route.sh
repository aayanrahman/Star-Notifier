#!/bin/zsh
# usage: route.sh <in.kicad_pcb> <out.kicad_pcb> <tag>  -- GND is left to the pours
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
T=../tools
$PY -c "import pcbnew; b=pcbnew.LoadBoard('$1'); pcbnew.ExportSpecctraDSN(b,'$3.dsn')" 2>/dev/null
python3 - $3.dsn <<'PYEOF'
import re, sys
p = sys.argv[1]
s = open(p).read()
s, n = re.subn(r'\(net GND\s*\(pins[^)]*\)\s*\)', '(net GND)', s)
print('stripped GND pins:', n)
# route narrow; power gets widened afterwards wherever it fits
def setw(cls, w, c):
    global s
    s = re.sub(r'(\(class ' + re.escape(cls) + r' [^\n]*(?:\n(?!\s*\(class)[^\n]*)*?\(width )\d+(\)\s*\(clearance )\d+', lambda m: m.group(1) + str(w) + m.group(2) + str(c), s, count=1)
for cls, w in [('kicad_default', 200), ('Power', 400), ('3V3', 400), ('VBUS', 400), ('USB', 200), ('GND', 400)]:
    setw(cls, w, 150)
s = s.replace('(clearance 200)\n      (clearance 50 (type smd_smd))', '(clearance 150)\n      (clearance 50 (type smd_smd))')
open(p, 'w').write(s)
PYEOF
$T/java -Djava.awt.headless=true -jar $T/freerouting.jar --gui.enabled=false -de $3.dsn -do $3.ses -mp 150 > $3.log 2>&1
$PY -c "import pcbnew; b=pcbnew.LoadBoard('$1'); pcbnew.ImportSpecctraSES(b,'$3.ses'); pcbnew.SaveBoard('$2',b)" 2>/dev/null
cp ${1%.kicad_pcb}.kicad_pro ${2%.kicad_pcb}.kicad_pro
grep -A30 "could not be routed" $3.log | grep -E "Net|->"
grep "Auto-routing stage completed" $3.log | sed 's/.*final score/score/'
