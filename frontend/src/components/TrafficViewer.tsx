import React, { useMemo, useState } from 'react'

type Frame = { ts:number, id_hex:string, pgn?:number, sa?:number, data_hex:string, decoded?:Record<string,any>, name?:string }

export default function TrafficViewer({frames}:{frames:Frame[]}){
  const [pgnFilter, setPgnFilter] = useState<string>('')
  const [text, setText] = useState<string>('')

  const filtered = useMemo(()=>{
    return frames.filter(f=>{
      if (pgnFilter){
        if (!f.pgn || String(f.pgn) !== pgnFilter.trim()) return false
      }
      if (text){
        const hay = `${f.id_hex} ${f.data_hex} ${f.name||''} ${JSON.stringify(f.decoded||{})}`.toLowerCase()
        if (!hay.includes(text.toLowerCase())) return false
      }
      return true
    })
  }, [frames, pgnFilter, text])

  return (
    <div className="bg-white rounded-2xl shadow p-2">
      <div className="flex items-center justify-between px-2 py-1 gap-2">
        <div className="font-semibold">Live Traffic ({filtered.length}/{frames.length})</div>
        <div className="flex items-center gap-2 text-sm">
          <input placeholder="Filter PGN e.g. 65262" className="border rounded px-2 py-1" value={pgnFilter} onChange={e=>setPgnFilter(e.target.value)} />
          <input placeholder="Search text…" className="border rounded px-2 py-1" value={text} onChange={e=>setText(e.target.value)} />
        </div>
      </div>
      <div className="overflow-auto max-h-[60vh]">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-zinc-100">
            <tr>
              <th className="text-left p-2">Time</th>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">PGN</th>
              <th className="text-left p-2">SA</th>
              <th className="text-left p-2">Data</th>
              <th className="text-left p-2">Decoded</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f,idx)=> (
              <tr key={idx} className="odd:bg-zinc-50">
                <td className="p-2">{typeof f.ts === 'number' ? f.ts.toFixed(3) : f.ts}</td>
                <td className="p-2 font-mono">{f.id_hex}</td>
                <td className="p-2">{f.pgn}</td>
                <td className="p-2">{f.sa}</td>
                <td className="p-2 font-mono">{f.data_hex}</td>
                <td className="p-2">
                  <div className="text-xs">{f.name}</div>
                  <div className="text-xs">{f.decoded ? Object.entries(f.decoded).map(([k,v])=>`${k}: ${v}`).join(', ') : ''}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
