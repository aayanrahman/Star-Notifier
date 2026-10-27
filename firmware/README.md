# Firmware: BLE breadboard demo

An ESP32 on a breadboard with one LED. While Claude Code is working, the LED
pulses in time with the Claude Code spinner. When Claude finishes, it stays lit.
When Claude needs your input, it breathes.

```
Claude Code hook → mac/notify.py → Bluetooth LE → ESP32 → LED
```

## 1. Wire the LED

```
GPIO 2 ──[ 220–330 Ω ]──►|── GND
                     long leg  short leg
```

Any free GPIO works. Change `LED_PIN` at the top of the sketch if you use another one.
If you skip the external LED, many dev boards have a built-in LED on GPIO 2.

## 2. Flash it (Arduino IDE)

1. **Board support:** in *Boards Manager*, install **esp32 by Espressif Systems**.
2. **Open the sketch:** open `StarNotifierBLE/StarNotifierBLE.ino`.
3. **Pick your board:** *Tools → Board → esp32 →* your board. "ESP32 Dev Module" works for most plain ESP32 boards; pick the C3 or S3 entry if that's what you have. Then choose the port.
4. **Upload.** If it hangs on "Connecting…", hold the board's **BOOT** button until the upload starts.
5. **Check it booted:** open the Serial Monitor at 115200. You should see `Advertising as Star-Notifier`, and the LED blinks twice.

Once it's flashed it doesn't need the laptop. Any USB power works, as long as it's
within Bluetooth range of the Mac.

## 3. Set up the Mac

```sh
python3 -m venv ~/.star-notifier
~/.star-notifier/bin/pip install bleak
~/.star-notifier/bin/python firmware/mac/notify.py test
```

The first run makes macOS ask for Bluetooth access for your terminal app. Allow it,
then run it again. The LED should strobe, and the Serial Monitor shows `Command: test`.

Each command takes a second or two, because the script finds the board and
connects fresh every time.

## 4. Hook it up to Claude Code

Add this to `~/.claude/settings.json`, using the full path to `notify.py`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [{ "type": "command", "command": "~/.star-notifier/bin/python /path/to/Star-Notifier/firmware/mac/notify.py done >/dev/null 2>&1 &" }] }
    ],
    "Notification": [
      { "hooks": [{ "type": "command", "command": "~/.star-notifier/bin/python /path/to/Star-Notifier/firmware/mac/notify.py wait >/dev/null 2>&1 &" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "~/.star-notifier/bin/python /path/to/Star-Notifier/firmware/mac/notify.py work >/dev/null 2>&1 &" }] }
    ]
  }
}
```

- `UserPromptSubmit` runs when you send a message, so the LED starts the spinner pulse.
- `Stop` runs when Claude finishes a reply, so the LED stays lit.
- `Notification` runs when Claude is waiting on you, for example for a permission prompt, so the LED breathes.

The `&` at the end runs each command in the background, so Claude never waits on Bluetooth.

## Commands

| Write | LED |
|---|---|
| `work` | steps up and down like the Claude Code spinner, about 1.2 s per cycle |
| `done` | solid on until the next command |
| `test` | 3 strobe bursts, then off |
| `wait` | slow breathing until the next command |
| `off` | off |

## If it doesn't work

- **"Star-Notifier not found":** check the board is powered and the Serial Monitor says it's advertising. Also turn Bluetooth off and on on the Mac.
- **The LED is on when it should be off:** your LED is wired active-low. Set `LED_ACTIVE_LOW = true`.
- **Compile error about BLE:** your board has no Bluetooth (the ESP32-S2 doesn't), or the wrong board is selected.
