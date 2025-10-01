from typing import Dict, Any

def safe_hex(data: bytes) -> str:
    return data.hex().upper()

def _u16(lo:int, hi:int)->int:
    return (hi<<8)|lo

def _is_na(b:int)->bool:
    return b==0xFF

def decode_frame(fr)->Dict[str,Any]:
    try:
        arb=int(fr.id_hex,16)
    except Exception:
        return {'pgn':None,'sa':None,'decoded':{}}
    pdu_format=(arb>>16)&0xFF
    pdu_specific=(arb>>8)&0xFF
    sa=arb&0xFF
    pgn=(pdu_format<<8)|pdu_specific if pdu_format>=240 else (pdu_format<<8)
    b=list(fr.data)+[0]*(8-len(fr.data))
    d={}
    if pgn==65253:
        raw=b[0]|(b[1]<<8)|(b[2]<<16)|(b[3]<<24)
        d['Engine Hours (h)']='N/A' if 0xFF in b[0:4] else round(raw*0.05,3)
    if pgn==65262:
        d['Coolant Temp (°C)']='N/A' if _is_na(b[0]) else (b[0]-40)
        d['Fuel Temp (°C)']='N/A' if _is_na(b[1]) else (b[1]-40)
        if _is_na(b[2]) or _is_na(b[3]): d['Oil Temp (°C)']='N/A'
        else:
            raw=_u16(b[2],b[3])
            d['Oil Temp (°C)']=round((raw/32.0)-273.0,3)
    if pgn==65263:
        d['Fuel Delivery Pressure (kPa)']='N/A' if _is_na(b[0]) else b[0]*4
        d['Engine Oil Pressure (kPa)']='N/A' if _is_na(b[3]) else b[3]*4
        d['Coolant Pressure (kPa)']='N/A' if _is_na(b[6]) else b[6]*2
        d['Coolant Level (%)']='N/A' if _is_na(b[7]) else round(b[7]*0.4,3)
    if pgn==65272:
        d['Trans Oil Pressure (kPa)']='N/A' if _is_na(b[3]) else b[3]*16
        if _is_na(b[4]) or _is_na(b[5]): d['Trans Oil Temp (°C)']='N/A'
        else:
            raw=_u16(b[4],b[5])
            d['Trans Oil Temp (°C)']=round((raw/32.0)-273.0,3)
    if pgn==65266:
        if _is_na(b[0]) or _is_na(b[1]): d['Fuel Rate (L/h)']='N/A'
        else:
            raw=_u16(b[0],b[1])
            d['Fuel Rate (L/h)']=round(raw*0.05,3)
        if _is_na(b[4]) or _is_na(b[5]): d['Avg Fuel Economy (km/L)']='N/A'
        else:
            raw=_u16(b[4],b[5])
            d['Avg Fuel Economy (km/L)']=round(raw/512.0,3)
    if pgn==65276:
        d['Fuel Level (%)']='N/A' if _is_na(b[1]) else round(b[1]*0.4,3)
    if pgn==61443:
        d['Engine Load (%)']='N/A' if _is_na(b[2]) else b[2]*1.0
    return {'pgn':pgn,'sa':sa,'decoded':d}
