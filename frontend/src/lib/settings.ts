// frontend/src/lib/settings.ts
export function getApiBase(): string {
  // read from browser storage (set by SettingsPanel)
  const ls = (typeof window !== 'undefined') ? window.localStorage.getItem('apiBase') : null
  if (ls && ls.trim()) return ls.trim()
  // fallback when nothing stored yet:
  return (import.meta.env.VITE_API_BASE as string) || 'http://localhost:8000'
}

export function setApiBase(v: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('apiBase', v)
}

export function getDefaultInterface(): string {
  if (typeof window === 'undefined') return 'vcan0'
  return window.localStorage.getItem('defaultInterface') || 'vcan0'
}

export function setDefaultInterface(v: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('defaultInterface', v)
}
