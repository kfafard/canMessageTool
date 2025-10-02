import React, { useMemo, useState } from "react"
import { sendFrames } from "../lib/api"

type Field = {
  key: string
  label: string
  unit?: string
  type: "u8" | "u16"
  /**
   * scale is “engineering units per bit”.
   *   e.g. 16 kPa/bit → scale=16
   *   0.4 %/bit → scale=0.4
   * For temperatures with Kelvin storage (1/32 K/bit), set scale=1/32 and offsetK=273.0.
   * For +40 °C signed range (J1939 style) use offsetC=40 with scale=1.
   */
  scale?: number
  /** byte index (0..7) for u8, little-endian start byte for u16 */
  byte: number
  /** optional engineering offset in °C (added before scaling) */
  offsetC?: number
  /** optional Kelvin offset for 1/32 K encodings (added before scaling in K) */
  offsetK?: number
}

type PGNDef = {
  pgn: number
  id_hex: string
  name: string
  fields: Field[]
  /** if present, used to render a hint under the fields */
  hint?: string
}

function toHEX(bytes: Uint8Array) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("").toUpperCase()
}

function putU16LE(b: Uint8Array, idx: number, raw: number) {
  b[idx] = raw & 0xFF
  b[idx + 1] = (raw >> 8) & 0xFF
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n))
}

/** Snap a u8 with given scale to raw (0..0xFE), 0xFF=NA kept if value is NaN */
function snapU8(v: number | undefined, scale: number) {
  if (v == null || Number.isNaN(v)) return undefined
  const raw = Math.round(v / scale)
  return clamp(raw, 0, 0xFE)
}

/** Snap a u16 with given scale to raw (0..0xFFFE), 0xFFFF=NA kept if value is NaN */
function snapU16(v: number | undefined, scale: number) {
  if (v == null || Number.isNaN(v)) return undefined
  const raw = Math.round(v / scale)
  return clamp(raw, 0, 0xFFFE)
}

/** Snap for u16 temperatures encoded in 1/32 K with 273.0 K offset to match your decoder */
function snapU16_TempC_1over32K(vC: number | undefined) {
  if (vC == null || Number.isNaN(vC)) return undefined
  // scale = 1/32 K per bit → raw = (T[K]) / (1/32) = (T[K]) * 32
  const raw = Math.round((vC + 273.0) * 32)
  return clamp(raw, 0, 0xFFFE)
}

/** Snap for u8 temps with +40 °C offset (J1939) */
function snapU8_TempC_plus40(vC: number | undefined) {
  if (vC == null || Number.isNaN(vC)) return undefined
  const raw = Math.round(vC + 40)
  return clamp(raw, 0, 0xFE)
}

/** Engine hours 0.05 h/bit → 32-bit LE value across bytes 0..3 */
function putEngineHours(b: Uint8Array, hours: number | undefined) {
  if (hours == null || Number.isNaN(hours)) return
  const raw = Math.round(hours / 0.05) >>> 0
  // 32-bit little endian into bytes 0..3
  b[0] = raw & 0xFF
  b[1] = (raw >> 8) & 0xFF
  b[2] = (raw >> 16) & 0xFF
  b[3] = (raw >> 24) & 0xFF
}

/**
 * PGNs with byte mappings & exact scales/offsets,
 * all bytes default NA (0xFF) unless written by a field.
 */
const PGNS: PGNDef[] = [
  // 65253 – Engine Hours (SPN 247) 0.05 h/bit across bytes 0..3, LE
  {
    pgn: 65253,
    id_hex: "18FEE5FF",
    name: "Engine Hours",
    fields: [
      { key: "hours", label: "Engine Hours", unit: "h", type: "u16", scale: 0.05, byte: 0 }, // handled specially
    ],
    hint: "Hours: 0.05 h/bit (4 bytes, little-endian)."
  },

  // 65262 – Coolant/Fuel/Oil temps
  // b0: Coolant Temp (°C) = raw - 40  → 1 °C/bit, 0xFF = NA
  // b1: Fuel Temp    (°C) = raw - 40  → 1 °C/bit, 0xFF = NA
  // b2..b3: Oil Temp (°C) stored as (T[K]*32), LE, 0xFFFF = NA
  {
    pgn: 65262,
    id_hex: "18FEEEFF",
    name: "Temps",
    fields: [
      { key: "cool", label: "Coolant Temp", unit: "°C", type: "u8",  scale: 1, byte: 0, offsetC: 40 },
      { key: "fuel", label: "Fuel Temp",    unit: "°C", type: "u8",  scale: 1, byte: 1, offsetC: 40 },
      { key: "oil",  label: "Oil Temp",     unit: "°C", type: "u16", scale: 1/32, byte: 2, offsetK: 273.0 },
    ],
    hint: "Coolant/Fuel: 1 °C/bit with +40 °C offset (0xFF=NA). Oil: 1/32 K/bit, +273.0 K (0xFFFF=NA)."
  },

  // 65263 – Pressures & Coolant Level
  // b0: Fuel Delivery Pressure (4 kPa/bit)
  // b3: Engine Oil Pressure   (4 kPa/bit)
  // b6: Coolant Pressure      (2 kPa/bit)
  // b7: Coolant Level         (0.4 %/bit)
  {
    pgn: 65263,
    id_hex: "18FEEFFF",
    name: "Pressures & Coolant Level",
    fields: [
      { key: "fuel_del_kpa", label: "Fuel Delivery Pressure", unit: "kPa", type: "u8",  scale: 16/4, byte: 0 }, // keep exact 4 kPa/bit (scale=4), noted below
      { key: "oil_kpa",      label: "Engine Oil Pressure",   unit: "kPa", type: "u8",  scale: 4,    byte: 3 },
      { key: "cool_kpa",     label: "Coolant Pressure",      unit: "kPa", type: "u8",  scale: 2,    byte: 6 },
      { key: "level_pct",    label: "Coolant Level",         unit: "%",   type: "u8",  scale: 0.4,  byte: 7 },
    ],
    hint: "Fuel Del: 4 kPa/bit, Oil: 4 kPa/bit, Coolant Press: 2 kPa/bit, Coolant Level: 0.4 %/bit."
  },

  // 65272 – Transmission Oil (TF1)
  // b3: Pressure (16 kPa/bit)
  // b4..b5: Temp (1/32 K/bit, +273.0 K), LE
  {
    pgn: 65272,
    id_hex: "18FEF8FF",
    name: "Transmission Oil (TF1)",
    fields: [
      { key: "press_kpa", label: "Pressure", unit: "kPa", type: "u8",  scale: 16,   byte: 3 },
      { key: "temp_c",    label: "Temp",     unit: "°C",  type: "u16", scale: 1/32, byte: 4, offsetK: 273.0 },
    ],
    hint: "Pressure: 16 kPa/bit (0xFF=NA). Temp: 1/32 K/bit, +273.0 K (0xFFFF=NA, LE)."
  },

  // 65266 – Fuel Rate & Avg FE
  // b0..b1: Fuel Rate (0.05 L/h/bit), LE
  // b4..b5: Avg Fuel Economy (km/L) with 1/512 km/L per bit, LE
  {
    pgn: 65266,
    id_hex: "18FEF2FF",
    name: "Fuel Rate & Avg FE",
    fields: [
      { key: "rate_lph",  label: "Fuel Rate",        unit: "L/h",  type: "u16", scale: 0.05,  byte: 0 },
      { key: "avg_kmpl",  label: "Avg Fuel Economy", unit: "km/L", type: "u16", scale: 1/512, byte: 4 },
    ],
    hint: "Rate: 0.05 L/h/bit (LE). Avg FE: 1/512 km/L per bit (LE)."
  },

  // 65276 – Fuel Level
  // b1: Fuel Level (0.4 %/bit)
  {
    pgn: 65276,
    id_hex: "18FEFCFF",
    name: "Fuel Level",
    fields: [
      { key: "fuel_pct", label: "Fuel Level", unit: "%", type: "u8", scale: 0.4, byte: 1 },
    ],
    hint: "Fuel level: 0.4 %/bit (0xFF=NA)."
  },

  // 61443 – Engine Load
  // b2: Engine Load (1 %/bit)
  {
    pgn: 61443,
    id_hex: "18F003FF",
    name: "Engine Load",
    fields: [
      { key: "load_pct", label: "Engine Load", unit: "%", type: "u8", scale: 1, byte: 2 },
    ],
    hint: "Engine load: 1 %/bit (0xFF=NA)."
  },
]

// For nicer inputs: suggest steps that match representable values per-field.
const INPUT_STEPS: Record<string, number> = {
  press_kpa: 16,     // TF1 pressure
  fuel_del_kpa: 4,
  oil_kpa: 4,
  cool_kpa: 2,
  level_pct: 0.4,
  fuel_pct: 0.4,
  rate_lph: 0.05,
  avg_kmpl: 1/512,
  load_pct: 1,
  cool: 1,
  fuel: 1,
  temp_c: 1,         // free, but encode snaps exactly
  oil: 1,            // free, but encode snaps exactly
  hours: 0.05,
}

export default function MessageBuilder() {
  const [pgnIdx, setPgnIdx] = useState(0)
  const [vals, setVals] = useState<Record<string, number>>({})
  const def = PGNS[pgnIdx]

  // Build 8-byte payload with correct snapping/encodings
  const dataHex = useMemo(() => {
    const b = new Uint8Array(8).fill(0xFF)

    if (def.pgn === 65253) {
      putEngineHours(b, num(vals["hours"]))
      return toHEX(b)
    }

    for (const f of def.fields) {
      const v = num(vals[f.key])
      if (v == null) continue

      // Special temperature forms:
      if (f.type === "u8" && f.offsetC === 40 && f.scale === 1) {
        const raw = snapU8_TempC_plus40(v)
        if (raw !== undefined) b[f.byte] = raw
        continue
      }
      if (f.type === "u16" && f.offsetK === 273.0 && f.scale === 1/32) {
        const raw = snapU16_TempC_1over32K(v)
        if (raw !== undefined) putU16LE(b, f.byte, raw)
        continue
      }

      // Generic u8 / u16 scaled signals:
      if (f.type === "u8" && f.scale != null) {
        const raw = snapU8(v, f.scale)
        if (raw !== undefined) b[f.byte] = raw
        continue
      }
      if (f.type === "u16" && f.scale != null) {
        const raw = snapU16(v, f.scale)
        if (raw !== undefined) putU16LE(b, f.byte, raw)
        continue
      }
    }

    return toHEX(b)
  }, [def, vals])

  function num(x: any): number | undefined {
    if (x === "" || x == null) return undefined
    const n = Number(x)
    return Number.isNaN(n) ? undefined : n
  }

  function setField(k: string, v: string) {
    const n = v === "" ? undefined : Number(v)
    setVals(prev => ({ ...prev, [k]: n as any }))
  }

  async function handleSend() {
    await sendFrames([{ id_hex: def.id_hex, data_hex: dataHex }])
  }

  return (
    <div className="space-y-2">
      <div className="fg-strong text-sm font-semibold">Message Builder</div>

      {/* PGN selector */}
      <div className="flex items-center gap-2">
        <label className="text-xs fg-muted w-10">PGN</label>
        <select
          className="input w-full"
          value={pgnIdx}
          onChange={(e) => { setPgnIdx(Number(e.target.value)); setVals({}) }}
        >
          {PGNS.map((p, i) => (
            <option key={p.pgn} value={i}>{p.pgn} – {p.name}</option>
          ))}
        </select>
      </div>

      {/* Fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {def.fields.map(f => (
          <label key={f.key} className="flex items-center gap-2">
            <span className="w-40 fg-base text-sm">
              {f.label}{f.unit ? ` (${f.unit})` : ""}
            </span>
            <input
              className="input w-36"
              type="number"
              step={INPUT_STEPS[f.key] ?? 1}
              value={vals[f.key] ?? ""}
              onChange={(e) => setField(f.key, e.target.value)}
            />
          </label>
        ))}
      </div>

      {def.hint && <div className="text-xs fg-muted">{def.hint}</div>}

      {/* Inline ID/DATA + buttons */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono fg-base truncate">
          ID {def.id_hex}&nbsp;&nbsp;DATA {dataHex}
        </div>
        <div className="flex gap-2">
          <button className="btn-primary" onClick={handleSend}>Send</button>
          <button className="btn" onClick={() => setVals({})}>Reset</button>
        </div>
      </div>
    </div>
  )
}
