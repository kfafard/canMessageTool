from decoder import decode_frame
from types import SimpleNamespace

def mkframe(id_hex, data_hex):
    return SimpleNamespace(id_hex=id_hex, data=bytes.fromhex(data_hex))

def test_engine_hours():
    fr = mkframe("18FEE5FF", "A0860100FFFFFFFF")
    out = decode_frame(fr)
    assert out["pgn"] == 65253
    assert round(out["decoded"]["Engine Hours (h)"],2) == 5000.0

def test_temps():
    fr = mkframe("18FEEEFF", "2241602DFFFFFFFF")
    out = decode_frame(fr)
    assert out["decoded"]["Coolant Temp (°C)"] == -6
    assert out["decoded"]["Fuel Temp (°C)"] == 25
    assert round(out["decoded"]["Oil Temp (°C)"],1) == 90.0
