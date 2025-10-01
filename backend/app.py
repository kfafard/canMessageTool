from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
import asyncio, json, io, time
from bus import BusManager, Frame
from decoder import decode_frame, safe_hex
from j1939_maps import PGN_NAME_MAP
from models import ConnectRequest, SendRequest, LogStartRequest


app=FastAPI(title='CAN Tool Backend', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
bus_manager=BusManager()
logging_enabled=False
log_buffer=['timestamp,id_hex,pgn,sa,data_hex,decoded_json\n']

@app.get('/api/interfaces')
async def list_interfaces():
    detected = await bus_manager.discover_interfaces()
    base = ['vcan0', 'can0']
    uniq = list(dict.fromkeys(base + detected))
    return {'interfaces': uniq}

@app.post('/api/connect')
async def connect(req: ConnectRequest):
    ok, msg = await bus_manager.connect(req.channel, bitrate=req.bitrate)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        'status': 'connected',
        'channel': req.channel,
        'info': bus_manager.health_snapshot()
    }

@app.post('/api/selftest')
async def selftest():
    return await bus_manager.selftest(timeout_ms=300)


@app.post('/api/disconnect')
async def disconnect():
    await bus_manager.disconnect()
    return {'status':'disconnected'}

@app.get('/api/health')
async def health():
    return bus_manager.health_snapshot()

@app.post('/api/send')
async def send(req: SendRequest):
    out=[]
    for it in req.frames:
        try:
            await bus_manager.send(it['id_hex'], it['data_hex'])
            out.append({'id_hex':it['id_hex'],'ok':True})
        except Exception as e:
            out.append({'id_hex':it['id_hex'],'ok':False,'error':str(e)})
    return {'results': out}

@app.get('/api/presets')
async def get_presets():
    with open('presets.json','r') as f:
        return json.load(f)

@app.post('/api/presets')
async def save_presets(payload: Dict[str,Any]):
    with open('presets.json','w') as f:
        json.dump(payload,f,indent=2)
    return {'status':'ok'}

@app.get('/api/groups')
async def get_groups():
    try:
        with open('groups.json','r') as f: return json.load(f)
    except FileNotFoundError:
        return {'groups': []}

@app.post('/api/groups')
async def save_groups(payload: Dict[str,Any]):
    with open('groups.json','w') as f:
        json.dump(payload,f,indent=2)
    return {'status':'ok'}

@app.post('/api/log/start')
async def log_start(req: LogStartRequest):
    global logging_enabled, log_buffer
    logging_enabled=True
    log_buffer=['timestamp,id_hex,pgn,sa,data_hex,decoded_json\n']
    return {'status':'logging'}

@app.post('/api/log/stop')
async def log_stop():
    global logging_enabled
    logging_enabled=False
    content=''.join(log_buffer).encode('utf-8')
    return {'csv': content.decode('utf-8')}

@app.websocket('/api/stream')
async def stream(ws: WebSocket):
    await ws.accept()

    # One-time connection snapshot so the UI can show a banner/badge
    await ws.send_json({
        'type': 'connected',
        'info': bus_manager.health_snapshot()
    })

    try:
        while True:
            batch = await bus_manager.get_rx_batch(timeout=0.02, max_items=200)
            items = []
            for fr in batch:
                dec = decode_frame(fr)
                items.append({
                    'ts': fr.ts,
                    'id_hex': fr.id_hex,
                    'data_hex': safe_hex(fr.data),
                    'pgn': dec.get('pgn'),
                    'sa': dec.get('sa'),
                    'decoded': dec.get('decoded'),
                    'name': PGN_NAME_MAP.get(dec.get('pgn'))
                })
            if items:
                await ws.send_json({'type': 'frames', 'items': items})
            else:
                await asyncio.sleep(0.05)
                await ws.send_json({'type': 'health', 'value': bus_manager.health_snapshot()})
    except WebSocketDisconnect:
        return
