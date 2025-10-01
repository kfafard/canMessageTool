#!/usr/bin/env python3
# Sends all presets to vcan0 for quick e2e check.

import json, time
import can

with open("presets.json","r") as f:
    presets = json.load(f)["presets"]

bus = can.interface.Bus("vcan0", bustype="socketcan")

for p in presets:
    arb = int(p["id_hex"], 16)
    data = bytes.fromhex(p["data_hex"])
    msg = can.Message(arbitration_id=arb, data=data, is_extended_id=True)
    print("Sending", p["name"], p["id_hex"], p["data_hex"])
    bus.send(msg)
    time.sleep(0.05)

print("Done")
