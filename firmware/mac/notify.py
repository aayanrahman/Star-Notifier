"""Send a command to the Star Notifier over Bluetooth LE.

    notify.py done   # strobe
    notify.py wait   # breathe until the next command
    notify.py off

Finds the board by its service UUID, connects, writes, and disconnects.
Exits quietly with status 1 if the board isn't nearby, so a Claude Code hook
never gets stuck on it.
"""

import asyncio
import sys

from bleak import BleakClient, BleakScanner

SERVICE_UUID = "12dfac1e-0b86-4adf-8fc9-59cbe90f7db7"
COMMAND_UUID = "9887946c-c769-4e25-95b7-fc4080034d02"
NAME = "Star-Notifier"


async def send(command: str) -> bool:
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: d.name == NAME or SERVICE_UUID in adv.service_uuids,
        timeout=8.0,
    )
    if device is None:
        print("Star-Notifier not found. Is it powered and nearby?", file=sys.stderr)
        return False

    async with BleakClient(device) as client:
        await client.write_gatt_char(COMMAND_UUID, command.encode(), response=True)
    print(f"sent {command!r} to {device.name or device.address}")
    return True


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "done"
    sys.exit(0 if asyncio.run(send(command)) else 1)
