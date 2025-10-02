import React, { useEffect, useRef, useState } from "react"
import {
  getInterfaces,
  connect as apiConnect,
  disconnect,
  streamSocket,
  getPresets,
  sendFrames,
} from "./lib/api"
import ConnectPanel from "./components/ConnectPanel"
import TrafficViewer from "./components/TrafficViewer"
import PresetsPanel from "./components/PresetsPanel"
import MessageBuilder from "./components/MessageBuilder"

// Dark mode toggle
function useDarkMode() {
  const [dark, setDark] = useState<boolean>(() => {
    const saved = localStorage.getItem("theme")
    if (saved) return saved === "dark"
    return window.matchMedia?.( "(prefers-color-scheme: dark)" as any ).matches ?? false
  })
  useEffect(() => {
    const root = document.documentElement
    if (dark) { root.classList.add("dark");  localStorage.setItem("theme", "dark") }
    else      { root.classList.remove("dark");localStorage.setItem("theme", "light") }
  }, [dark])
  return { dark, setDark }
}

export default function App() {
  const { dark, setDark } = useDarkMode()

  const [ifs, setIfs] = useState<string[]>([])
  const [chan, setChan] = useState<string>("can0")
  const [connected, setConnected] = useState(false)
  const [frames, setFrames] = useState<any[]>([])
  const [presets, setPresets] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    getInterfaces().then((d) => setIfs(d || []))
    getPresets().then((d) => setPresets(d.presets || []))
  }, [])

  async function onConnect() {
  function normalizeFrame(x: any) {
    return {
      ts:
        typeof x?.ts === "number"
          ? x.ts
          : typeof x?.ts === "string"
          ? x.ts
          : "",
      id_hex: String(x?.id_hex ?? ""),
      pgn:
        typeof x?.pgn === "number"
          ? x.pgn
          : (x?.pgn && typeof x.pgn === "object" && "value" in x.pgn)
          ? x.pgn.value
          : "",
      sa: typeof x?.sa === "number" ? x.sa : "",
      data_hex: String(x?.data_hex ?? ""),
      decoded:
        typeof x?.decoded === "string"
          ? x.decoded
          : x?.decoded != null
          ? (() => {
              try { return JSON.stringify(x.decoded) } catch { return String(x.decoded) }
            })()
          : "",
    }
  }

  try {
    await apiConnect(chan)
    setConnected(true)

    const ws = streamSocket()
    wsRef.current = ws

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data?.type === "frames" && Array.isArray(data.items)) {
          const items = data.items.map(normalizeFrame)
          setFrames((prev) => {
            const next = [...items, ...(Array.isArray(prev) ? prev : [])]
            return next.slice(0, 10000)
          })
        } else {
          // non-frame messages are ignored safely
        }
      } catch (e) {
        console.error("WS parse/normalize error:", e)
      }
    }

    ws.onerror = (e) => console.error("WS error:", e)
    ws.onclose  = () => setConnected(false)
  } catch (e: any) {
    console.error("Connect failed:", e)
    alert(`Connect failed: ${e?.message || e}`)
  }
}

  async function onDisconnect() {
    try { await disconnect() } finally {
      setConnected(false)
      try { wsRef.current?.close() } catch {}
      wsRef.current = null
    }
  }

  function sendPreset(p: any) {
    sendFrames([{ id_hex: p.id_hex, data_hex: p.data_hex }])
  }

  
  return (
    <div className="min-h-screen bg-neutral-100 text-neutral-900 dark:bg-neutral-900 dark:text-neutral-100">
      <div className="w-full px-4 lg:px-6 py-3 space-y-3">

        {/* Header + theme toggle */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">CAN Tool</h1>
          <button
            className="btn"
            onClick={() => setDark(!dark)}
            title="Toggle dark mode"
          >
            {dark ? "🌙 Dark" : "☀️ Light"}
          </button>
        </div>

        {/* TOP ROW: Connection (7) + Message Builder (5) */}
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 lg:col-span-7">
            <div className="card p-3">
              <ConnectPanel
                interfaces={ifs}
                chan={chan}
                setChan={setChan}
                connected={connected}
                onConnect={onConnect}
                onDisconnect={onDisconnect}
              />
            </div>
          </div>

          <div className="col-span-12 lg:col-span-5">
            <div className="card p-3">
              {/* condensed builder (see component changes below) */}
              <MessageBuilder />
            </div>
          </div>
        </div>

        {/* BOTTOM ROW: Live Traffic (8) + Presets (4) with equal height */}
        <div className="grid grid-cols-12 gap-3">
          {/* same height for both panels; ~ viewport minus header + top row */}
          <div className="col-span-12 lg:col-span-9">
            <div className="card p-2 h-[calc(100vh-260px)] overflow-hidden">
              <div className="h-full">
                <TrafficViewer frames={frames} />
              </div>
            </div>
          </div>
          <div className="col-span-12 lg:col-span-3">
            <div className="card p-2 h-[calc(100vh-260px)] overflow-auto">
              <PresetsPanel presets={presets} onSend={sendPreset} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )

}
