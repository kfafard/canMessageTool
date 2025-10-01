// frontend/src/components/ConnectPanel.tsx
import React from "react"

type Props = {
  interfaces: string[]
  chan: string
  setChan: (v: string) => void
  connected: boolean
  onConnect: () => void
  onDisconnect: () => void
}

export default function ConnectPanel({
  interfaces,
  chan,
  setChan,
  connected,
  onConnect,
  onDisconnect,
}: Props) {
  return (
    <div className="bg-white rounded-2xl shadow p-3 space-y-2">
      <div className="font-semibold">Connection</div>

      <label className="text-sm flex items-center gap-2">
        <span className="w-32">Interface</span>
        <select
          className="border rounded px-2 py-1 flex-1"
          value={chan}
          onChange={(e) => setChan(e.target.value)}
        >
          {interfaces.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
      </label>

      {!connected ? (
        <button
          className="bg-green-600 text-white rounded px-3 py-1"
          onClick={onConnect}
        >
          Connect
        </button>
      ) : (
        <button
          className="bg-red-600 text-white rounded px-3 py-1"
          onClick={onDisconnect}
        >
          Disconnect
        </button>
      )}
    </div>
  )
}
