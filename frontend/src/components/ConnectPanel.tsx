import React, { useEffect, useState, useCallback } from "react"

type Status = {
  iface: string
  output?: string
  ok?: boolean
}

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
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<Status | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const BITRATE = 250_000

  // Parse "ip -br link show" output to infer UP/DOWN
  const linkState = (() => {
    const line = status?.output || ""
    if (/[\s:]UP(\s|$)/.test(line) || /state\s+UP/i.test(line)) return "UP"
    if (/DOWN/i.test(line)) return "DOWN"
    return "UNKNOWN"
  })()

  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true)
    try {
      const res = await fetch(`/api/can/status?iface=${encodeURIComponent(chan)}`)
      const data = (await res.json()) as Status
      setStatus(data)
    } catch {
      setStatus({ iface: chan, output: "status unavailable", ok: false })
    } finally {
      setLoadingStatus(false)
    }
  }, [chan])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus, chan, connected])

  async function bringUp() {
    setBusy(true)
    try {
      const res = await fetch("/api/can/bringup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ iface: chan, bitrate: BITRATE }),
      })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data.detail || "Bring-up failed")
      }
      // Refresh link status; no alert on success
      await fetchStatus()
    } catch (e: any) {
      // Only alert on failure (prevents the confusing "null bps" popup on vcan)
      alert(`Bring-up error: ${e?.message || e}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="fg-strong text-sm font-semibold">Connection</div>
        <div className="flex items-center gap-2">
          <span
            className={
              "text-xs px-2 py-0.5 rounded " +
              (linkState === "UP"
                ? "bg-green-600 text-white"
                : linkState === "DOWN"
                ? "bg-red-600 text-white"
                : "bg-gray-500 text-white")
            }
            title={status?.output || ""}
          >
            {chan}: {linkState}
          </span>
          <button className="btn-ghost" onClick={fetchStatus} disabled={loadingStatus}>
            {loadingStatus ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-center">
        <label className="text-xs fg-muted">Interface</label>
        <div className="md:col-span-2">
          <select
            className="input w-full"
            value={chan}
            onChange={(e) => setChan(e.target.value)}
            disabled={connected}
          >
            {(interfaces?.length ? interfaces : ["can0", "vcan0"]).map((i) => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
        </div>
      </div>

      {status?.output && (
        <div className="mt-2 text-[11px] font-mono text-fg-muted truncate">
          {status.output}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {!connected && (
          <button className="btn" disabled={busy} onClick={bringUp}>
            {busy ? "Bringing up…" : `Bring up ${chan} (${BITRATE.toLocaleString()} bps)`}
          </button>
        )}

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
