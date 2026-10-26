#!/bin/zsh
# build.sh <place_script.py> <tag> : place -> fanout -> freeroute -> widen/pour/stitch -> bridge -> DRC summary
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
t=$2
cp src.kicad_pro pl_$t.kicad_pro
$PY $1 src.kicad_pcb pl_$t.kicad_pcb >/dev/null 2>&1
cp pl_$t.kicad_pro fan_$t.kicad_pro
$PY fanout.py pl_$t.kicad_pcb fan_$t.kicad_pcb >/dev/null 2>&1
./route.sh fan_$t.kicad_pcb r_$t.kicad_pcb $t > route_$t.txt 2>&1      # copies the .kicad_pro itself
cp r_$t.kicad_pro po_$t.kicad_pro
$PY post.py r_$t.kicad_pcb po_$t.kicad_pcb > post_$t.txt 2>&1
cp po_$t.kicad_pro fin_$t.kicad_pro
$PY bridge.py po_$t.kicad_pcb fin_$t.kicad_pcb > bridge_$t.txt 2>&1
$CLI pcb drc --severity-error --severity-warning --refill-zones -o drc_$t.txt fin_$t.kicad_pcb >/dev/null 2>&1
echo "== $t: $(grep -E '^\[' drc_$t.txt | sed 's/:.*//' | grep -vE 'silk|text_height' | sort | uniq -c | tr '\n' ' ')"
grep -v "wxApp\|GetWidth" bridge_$t.txt
