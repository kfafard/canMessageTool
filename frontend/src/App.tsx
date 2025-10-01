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
// (optional) import other panels you use

export default function App() {
  const [ifs, setIfs] = useState<string[]>([])
  const [chan, setChan] = useState<string>("can0")   // <— default to can0 for you
  const [connected, setConnected] = useState(false)
  const [frames, setFrames] = useState<any[]>([])
  const [presets, setPresets] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Load available interfaces and presets on mount
    getInterfaces().then((d) => setIfs(d || []))
    getPresets().then((d) => setPresets(d.presets || []))
  }, [])

  async function onConnect() {
    try {
      // 1) ask backend to open the channel the user selected
      await apiConnect(chan)  // <— THIS is the actual open(can0)
      setConnected(true)

      // 2) start the WebSocket to receive live frames
      const ws = streamSocket()
      wsRef.current = ws
      ws.onmessage = (ev) => {
        const data = JSON.parse(ev.data)
        if (data.type === "frames") {
          setFrames((prev) => {
            const next = [...data.items, ...prev]
            return next.slice(0, 10000)
          })
        }
      }
      ws.onclose = () => setConnected(false)
    } catch (e: any) {
      alert(`Connect failed: ${e?.message || e}`)
    }
  }

  async function onDisconnect() {
    try {
      await disconnect()
    } finally {
      setConnected(false)
      try {
        wsRef.current?.close()
      } catch {}
      wsRef.current = null
    }
  }

  function sendPreset(p: any) {
    sendFrames([{ id_hex: p.id_hex, data_hex: p.data_hex }])
  }

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CAN Tool</h1>

      <ConnectPanel
        interfaces={ifs}
        chan={chan}
        setChan={setChan}
        connected={connected}
        onConnect={onConnect}
        onDisconnect={onDisconnect}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <TrafficViewer frames={frames} />
        </div>
        <div className="space-y-4">
          <PresetsPanel presets={presets} onSend={sendPreset} />
        </div>
      </div>
    </div>
  )
}
