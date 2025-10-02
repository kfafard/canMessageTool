import React, { useMemo, useState } from "react"
import { sendFrames } from "../lib/api"

type Preset = {
  id_hex: string
  data_hex: string
  title?: string
  expected?: string
}

export default function PresetsPanel({
  presets,
  onSend,
}: {
  presets: Preset[]
  onSend?: (p: Preset) => void
}) {
  // Manage selection locally by index
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const allSelected = useMemo(
    () => presets.length > 0 && selected.size === presets.length,
    [presets, selected]
  )

  const toggle = (idx: number, checked: boolean) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (checked) next.add(idx)
      else next.delete(idx)
      return next
    })
  }

  const clearSel = () => setSelected(new Set())

  const sendOne = (p: Preset) => {
    if (onSend) onSend(p)
    else sendFrames([{ id_hex: p.id_hex, data_hex: p.data_hex }])
  }

  const sendSelected = async () => {
    if (!selected.size) return
    const frames = [...selected].map(i => ({
      id_hex: presets[i].id_hex,
      data_hex: presets[i].data_hex,
    }))
    await sendFrames(frames)
  }

  const toggleAll = (checked: boolean) => {
    if (checked) setSelected(new Set(presets.map((_, i) => i)))
    else clearSel()
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold">Presets</div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost" onClick={clearSel}>Clear</button>
          <button
            className="btn-primary disabled:opacity-50"
            onClick={sendSelected}
            disabled={selected.size === 0}
          >
            Send Selected
          </button>
        </div>
      </div>

      {/* Make the whole column a bit skinnier/compact */}
      <div className="space-y-2 pr-1 max-w-[420px]">
        <label className="flex items-center gap-2 text-xs pl-1">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => toggleAll(e.target.checked)}
          />
          Select all
        </label>

        {presets.map((p, i) => (
          <div
            key={i}
            className="relative card px-3 py-2 text-sm"
          >
            {/* Checkbox top-left */}
            <div className="absolute left-2 top-2">
              <input
                type="checkbox"
                checked={selected.has(i)}
                onChange={(e) => toggle(i, e.target.checked)}
              />
            </div>

            {/* Send button top-right */}
            <div className="absolute right-2 top-2">
              <button className="btn-primary" onClick={() => sendOne(p)}>
                Send
              </button>
            </div>

            {/* Body */}
            <div className="pl-6 pr-24 space-y-1">
              <div className="font-mono text-xs">
                <span className="opacity-70 mr-2">ID</span> {p.id_hex}
                <span className="opacity-70 ml-3 mr-2">DATA</span> {p.data_hex}
              </div>
              {p.title && (
                <div className="text-xs opacity-80">{p.title}</div>
              )}
              {p.expected && (
                <div className="text-xs opacity-70">{p.expected}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
