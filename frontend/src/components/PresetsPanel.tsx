import React, { useMemo, useState } from 'react'
import { sendFrames } from '../lib/api'

export default function PresetsPanel({presets, onSend}:{presets:any[], onSend:(p:any)=>void}){
  const [checked, setChecked] = useState<Record<number, boolean>>({})
  const selected = useMemo(()=> presets.filter((_,i)=>checked[i]), [checked, presets])

  async function sendSelected(){
    if (!selected.length) return
    const frames = selected.map(p=>({id_hex:p.id_hex, data_hex:p.data_hex}))
    await sendFrames(frames)
  }

  return (
    <div className="bg-white rounded-2xl shadow p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold">Presets</div>
        <div className="flex gap-2">
          <button className="border rounded px-2 py-1 text-sm" onClick={()=>setChecked({})}>Clear</button>
          <button className="bg-blue-600 text-white rounded px-2 py-1 text-sm" onClick={sendSelected}>Send Selected</button>
        </div>
      </div>
      <div className="space-y-2">
        {presets.map((p:any, i:number)=>(
          <div className="border rounded-xl p-2 flex gap-2 items-start" key={i}>
            <input type="checkbox" className="mt-1" checked={!!checked[i]} onChange={e=>setChecked(s=>({...s, [i]: e.target.checked}))} />
            <div className="flex-1">
              <div className="text-sm font-medium">{p.name}</div>
              <div className="text-xs text-zinc-600 font-mono">ID {p.id_hex}  DATA {p.data_hex}</div>
              <div className="text-xs">Expected: {p.expected}</div>
              <button className="mt-2 bg-blue-600 text-white rounded px-3 py-1" onClick={()=>onSend(p)}>Send</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
