# autoroute-scripts

The pipeline that generated the star-shaped, routed `Star-Notifier.kicad_pcb`.

`build.sh <place_script.py> <tag>` runs these steps in order:

1. `place.py`: builds the rounded-star Edge.Cuts, places the parts and sets up the net classes.
2. `fanout.py`: adds the B.Cu no-track area under the ESP32 and a via for each GND pad.
3. `route.sh`: routes the board with Freerouting. GND is left out of the routing because the pours handle it.
4. `post.py`: widens the power traces, adds GND pours on both layers and adds stitching vias.
5. `bridge.py`: A* router that connects isolated GND pour islands back to the main ground.

## Requirements

- KiCad 10's bundled Python, at the path hard-coded in the scripts.
- Java 25 and `freerouting.jar`, both in `../tools`. They are not checked in.
- `src.kicad_pcb` / `src.kicad_pro` in the working directory as the input board.
