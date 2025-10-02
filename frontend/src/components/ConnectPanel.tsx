import React from "react"

export default function ConnectPanel({
  interfaces,
  chan,
  setChan,
  connected,
  onConnect,
  onDisconnect,
}: {
  interfaces: string[]
  chan: string
  setChan: (v: string) => void
  connected: boolean
  onConnect: () => Promise<void> | void
  onDisconnect: () => Promise<void> | void
}) {
  return (
    <div className="card p-3">
      <div className="fg-strong text-sm font-semibold mb-2">Connection</div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-center">
        <label className="text-xs fg-muted">Interface</label>
        <div className="md:col-span-2">
          <select
            className="input w-full"
            value={chan}
            onChange={(e) => setChan(e.target.value)}
            disabled={connected}
          >
            {interfaces?.length
              ? interfaces.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))
              : [<option key="can0">can0</option>]}
          </select>
        </div>
      </div>

      <div className="mt-3">
        {connected ? (
          <button className="btn" onClick={() => onDisconnect()}>
            Disconnect
          </button>
        ) : (
          <button className="btn-primary" onClick={() => onConnect()}>
            Connect
          </button>
        )}
      </div>
    </div>
  )
}
