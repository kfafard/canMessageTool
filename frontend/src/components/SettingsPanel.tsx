// frontend/src/components/SettingsPanel.tsx
import React, { useState } from 'react'
import { getApiBase, setApiBase, getDefaultInterface, setDefaultInterface } from '../lib/settings'

export default function SettingsPanel() {
  const [api, setApi] = useState(getApiBase())
  const [iface, setIface] = useState(getDefaultInterface())
  const [saved, setSaved] = useState(false)

  function save() {
    setApiBase(api)
    setDefaultInterface(iface)
    setSaved(true)
    setTimeout(() => setSaved(false), 1000)
    // reload so the app re-reads API base and reconnects using new settings
    window.location.reload()
  }

  return (
    <div className="bg-white rounded-2xl shadow p-3 space-y-2">
      <div className="font-semibold">Settings</div>

      <label className="text-sm flex items-center gap-2">
        <span className="w-40">API Base</span>
        <input
          className="border rounded px-2 py-1 flex-1"
          value={api}
          onChange={e => setApi(e.target.value)}
          placeholder="http://localhost:8000"
        />
      </label>

      <label className="text-sm flex items-center gap-2">
        <span className="w-40">Default Interface</span>
        <input
          className="border rounded px-2 py-1 flex-1"
          value={iface}
          onChange={e => setIface(e.target.value)}
          placeholder="vcan0"
        />
      </label>

      <button className="bg-zinc-800 text-white rounded px-3 py-1" onClick={save}>
        Save & Reload
      </button>

      {saved && <div className="text-green-700 text-xs">Saved.</div>}
      <div className="text-xs text-zinc-500">Values are stored in your browser (localStorage).</div>
    </div>
  )
}
