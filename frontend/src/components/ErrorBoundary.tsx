import React from "react"

type S = { error: Error | null }
export default class ErrorBoundary extends React.Component<React.PropsWithChildren, S> {
  state: S = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(err: Error, info: any) { console.error("ErrorBoundary:", err, info) }
  render() {
    if (this.state.error) {
      return (
        <div className="card p-3">
          <div className="fg-strong font-semibold mb-1">Something went wrong</div>
          <pre className="text-xs overflow-auto">{String(this.state.error)}</pre>
          <button className="btn mt-2" onClick={() => this.setState({ error: null })}>Dismiss</button>
        </div>
      )
    }
    return this.props.children
  }
}
