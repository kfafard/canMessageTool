import { getApiBase } from './settings'

const API_BASE = getApiBase()

export async function getInterfaces(): Promise<string[]> {
  const r = await fetch(`${API_BASE}/api/interfaces`)
  const d = await r.json()
  return d.interfaces || []
}

export async function connect(channel: string, bitrate?: number) {
  const r = await fetch(`${API_BASE}/api/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel, bitrate: bitrate ?? null }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function disconnect() {
  await fetch(`${API_BASE}/api/disconnect`, { method: 'POST' })
}

export function streamSocket(): WebSocket {
  const wsBase = API_BASE.replace('http', 'ws')
  return new WebSocket(`${wsBase}/api/stream`)
}

export async function getPresets() {
  const r = await fetch(`${API_BASE}/api/presets`)
  return r.json()
}

export async function sendFrames(frames: { id_hex: string; data_hex: string }[]) {
  const r = await fetch(`${API_BASE}/api/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frames }),
  })
  return r.json()
}
