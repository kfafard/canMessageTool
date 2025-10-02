import React from "react"

type Decoded = any // accept anything; we normalize at render time
type Frame = {
  time?: number | string
  id_hex: string
  pgn: number
  sa: number
  data_hex: string
  decoded?: Decoded | null
}

export default function TrafficViewer({ frames }: { frames: Frame[] }) {
  /** Render decoded in a human readable way no matter its shape */
  const renderDecoded = (d?: Decoded | null): React.ReactNode => {
    if (d == null) return ""

    // If it's a string, try JSON.parse, otherwise show as-is
    if (typeof d === "string") {
      try {
        const parsed = JSON.parse(d)
        return renderDecoded(parsed)
      } catch {
        return d
      }
    }

    // If it's an array, render each item on its own line
    if (Array.isArray(d)) {
      return d.map((item, idx) => (
        <div key={idx}>{flattenOne(item)}</div>
      ))
    }

    // If it's an object, render key: value lines
    if (typeof d === "object") {
      const entries = Object.entries(d).filter(
        ([, v]) => v !== undefined && v !== null && v !== ""
      )
      if (entries.length === 0) return ""
      return entries.map(([k, v]) => (
        <div key={k}>{k}: {flattenOne(v)}</div>
      ))
    }

    // number/boolean/etc
    return String(d)
  }

  /** Make a single value printable */
  const flattenOne = (v: unknown): string => {
    if (v == null) return ""
    if (typeof v === "object") {
      try {
        return JSON.stringify(v)
      } catch {
        return String(v)
      }
    }
    return String(v)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="text-sm font-semibold mb-2">Live Traffic ({frames.length})</div>

      <div className="flex-1 overflow-auto rounded-xl border border-borderc-light dark:border-borderc-dark">
        <table className="w-full text-sm table-fixed">
          <thead>
            <tr className="bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-100">
              <th className="text-left p-2 w-[120px]">Time</th>
              <th className="text-left p-2 w-[110px]">ID</th>
              <th className="text-left p-2 w-[80px]">PGN</th>
              <th className="text-left p-2 w-[70px]">SA</th>
              <th className="text-left p-2 w-[240px]">Data</th>
              {/* Wider decoded column; wraps instead of overflowing */}
              <th className="text-left p-2 w-[520px]">Decoded</th>
            </tr>
          </thead>

          <tbody>
            {frames.map((f, i) => (
              <tr key={i} className="odd:bg-neutral-50 dark:odd:bg-neutral-800">
                <td className="p-2 font-mono tabular-nums">{f.time ?? ""}</td>
                <td className="p-2 font-mono">{f.id_hex}</td>
                <td className="p-2 font-mono">{f.pgn}</td>
                <td className="p-2 font-mono">{f.sa}</td>
                <td className="p-2 font-mono">{f.data_hex}</td>
                <td className="p-2 align-top">
                  <div className="text-xs whitespace-pre-wrap break-words">
                    {renderDecoded(f.decoded)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
