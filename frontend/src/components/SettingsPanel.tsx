import React from "react"

export default function SettingsPanel({
  children,
  title = "Settings",
}: {
  children?: React.ReactNode
  title?: string
}) {
  return (
    <div className="card p-3">
      <div className="fg-strong text-sm font-semibold mb-2">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  )
}
