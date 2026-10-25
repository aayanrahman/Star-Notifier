# Star Notifier

A small star-shaped USB-C board that lights up when Claude Code or Cursor finishes a task.

- ESP32-C3-WROOM-02 with native USB serial
- 10× WS2812B-2020 LEDs, driven through a 74AHCT1G125 level shifter
- USB-C power (5.1k CC pull-downs, 500 mA polyfuse, USBLC6 ESD), AP2112K 3.3 V regulator
- 0603 passives, 2 layers

Status: schematic done (ERC clean). PCB, firmware and the hook are next.

Made in KiCad 10.
