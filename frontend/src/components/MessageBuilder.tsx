import React, { useMemo, useState } from 'react'
import { sendFrames } from '../lib/api'

type Field = { key:string, label:string, unit?:string, type:'u8'|'u16' }
type PGNDef = { pgn:number, id_hex:string, name:string, fields:Field[], build:(vals:Record<string,number>)=>string }

function hex(bytes:Uint8Array){
  return Array.from(bytes).map(b=>b.toString(16).padStart(2,'0')).join('').toUpperCase()
}
function putU16LE(bytes:Uint8Array, offset:number, value:number){
  const v = Math.max(0, Math.min(0xFFFF, Math.round(value)))
  bytes[offset] = v & 0xFF
  bytes[offset+1] = (v>>8) & 0xFF
}

const PGNS: PGNDef[] = [
  { pgn:65253, id_hex:'18FEE5FF', name:'Engine Hours',
    fields:[{key:'hours',label:'Engine Hours', unit:'h', type:'u16'}],
    build: (vals)=>{
      const hours = Number(vals['hours']||0)
      const raw = Math.round(hours / 0.05) >>> 0
      const b = new Uint8Array(8).fill(0xFF)
      b[0] = raw & 0xFF; b[1]=(raw>>8)&0xFF; b[2]=(raw>>16)&0xFF; b[3]=(raw>>24)&0xFF
      return hex(b)
    }
  },
  { pgn:65262, id_hex:'18FEEEFF', name:'Temps',
    fields:[
      {key:'cool',label:'Coolant Temp', unit:'°C', type:'u8'},
      {key:'fuel',label:'Fuel Temp', unit:'°C', type:'u8'},
      {key:'oil', label:'Oil Temp', unit:'°C', type:'u16'}
    ],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const cool = vals['cool']; if (cool!=null) b[0] = Math.max(0,Math.min(0xFE, Math.round(Number(cool) + 40)))
      const fuel = vals['fuel']; if (fuel!=null) b[1] = Math.max(0,Math.min(0xFE, Math.round(Number(fuel) + 40)))
      const oilC = vals['oil']; if (oilC!=null){
        const raw = Math.round((Number(oilC)+273)*32)
        putU16LE(b,2, raw)
      }
      return hex(b)
    }
  },
  { pgn:65263, id_hex:'18FEEFFF', name:'Pressures & Level',
    fields:[
      {key:'fuel_del_kpa', label:'Fuel Delivery Pressure', unit:'kPa', type:'u8'},
      {key:'oil_kpa', label:'Engine Oil Pressure', unit:'kPa', type:'u8'},
      {key:'cool_kpa', label:'Coolant Pressure', unit:'kPa', type:'u8'},
      {key:'level_pct', label:'Coolant Level', unit:'%', type:'u8'},
    ],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const fd = vals['fuel_del_kpa']; if (fd!=null) b[0] = Math.max(0,Math.min(0xFE, Math.round(Number(fd)/4)))
      const oil = vals['oil_kpa']; if (oil!=null) b[3] = Math.max(0,Math.min(0xFE, Math.round(Number(oil)/4)))
      const cp = vals['cool_kpa']; if (cp!=null) b[6] = Math.max(0,Math.min(0xFE, Math.round(Number(cp)/2)))
      const lvl = vals['level_pct']; if (lvl!=null) b[7] = Math.max(0,Math.min(0xFE, Math.round(Number(lvl)/0.4)))
      return hex(b)
    }
  },
  { pgn:65272, id_hex:'18FEF8FF', name:'Trans Oil',
    fields:[
      {key:'press_kpa', label:'Pressure', unit:'kPa', type:'u8'},
      {key:'temp_c', label:'Temp', unit:'°C', type:'u16'},
    ],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const pr = vals['press_kpa']; if (pr!=null) b[3] = Math.max(0,Math.min(0xFE, Math.round(Number(pr)/16)))
      const t = vals['temp_c']; if (t!=null){ const raw = Math.round((Number(t)+273)*32); putU16LE(b,4,raw) }
      return hex(b)
    }
  },
  { pgn:65266, id_hex:'18FEF2FF', name:'Fuel Rate & Avg FE',
    fields:[
      {key:'rate_lph', label:'Fuel Rate', unit:'L/h', type:'u16'},
      {key:'avg_kmpl', label:'Avg Fuel Economy', unit:'km/L', type:'u16'},
    ],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const r = vals['rate_lph']; if (r!=null){ const raw = Math.round(Number(r)/0.05); putU16LE(b,0,raw) }
      const fe = vals['avg_kmpl']; if (fe!=null){ const raw = Math.round(Number(fe)*512); putU16LE(b,4,raw) }
      return hex(b)
    }
  },
  { pgn:65276, id_hex:'18FEFCFF', name:'Fuel Level',
    fields:[{key:'fuel_pct', label:'Fuel Level', unit:'%', type:'u8'}],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const pct = vals['fuel_pct']; if (pct!=null){ b[1] = Math.max(0,Math.min(0xFE, Math.round(Number(pct)/0.4)))}
      return hex(b)
    }
  },
  { pgn:61443, id_hex:'18F003FF', name:'Engine Load',
    fields:[{key:'load_pct', label:'Engine Load', unit:'%', type:'u8'}],
    build:(vals)=>{
      const b = new Uint8Array(8).fill(0xFF)
      const pct = vals['load_pct']; if (pct!=null) b[2] = Math.max(0,Math.min(0xFE, Math.round(Number(pct))))
      return hex(b)
    }
  },
]

export default function MessageBuilder(){
  const [pgnIdx, setPgnIdx] = useState(0)
  const [vals, setVals] = useState<Record<string, number>>({})
  const def = PGNS[pgnIdx]
  const dataHex = useMemo(()=> def.build(vals), [def, vals])

  function setField(k:string, v:string){
    const num = v === '' ? NaN : Number(v)
    setVals(prev => ({...prev, [k]: isNaN(num) ? undefined as any : num }))
  }

  async function handleSend(){
    await sendFrames([{id_hex: def.id_hex, data_hex: dataHex}])
  }

  return (
    <div className="bg-white rounded-2xl shadow p-3 space-y-3">
      <div className="font-semibold">Message Builder</div>
      <div className="flex gap-2 items-center">
        <label className="text-sm">PGN</label>
        <select className="border rounded px-2 py-1" value={pgnIdx} onChange={e=>{ setPgnIdx(Number(e.target.value)); setVals({}) }}>
          {PGNS.map((p, i)=>(<option key={p.pgn} value={i}>{p.pgn} – {p.name}</option>))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {def.fields.map(f => (
          <label key={f.key} className="text-sm flex items-center gap-2">
            <span className="w-48">{f.label}{f.unit ? ` (${f.unit})` : ''}</span>
            <input className="border rounded px-2 py-1 w-40" type="number" onChange={e=>setField(f.key, e.target.value)} />
          </label>
        ))}
      </div>

      <div className="text-xs font-mono">ID {def.id_hex}  DATA {dataHex}</div>
      <div className="flex gap-2">
        <button className="bg-blue-600 text-white rounded px-3 py-1" onClick={handleSend}>Send</button>
        <button className="border rounded px-3 py-1" onClick={()=>setVals({})}>Reset</button>
      </div>
    </div>
  )
}
