import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: "2rem",
          margin: "1rem",
          background: "#1e1e2e",
          border: "1px solid #ef4444",
          borderRadius: "12px",
          color: "#f4f7fb",
          textAlign: "center",
        }}>
          <span style={{ fontSize: "2rem" }}>⚠️</span>
          <h3 style={{ margin: "0.5rem 0", color: "#ef4444" }}>Something went wrong</h3>
          <p style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
            {this.state.error?.message || "An unexpected error occurred in this panel."}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: "0.75rem",
              padding: "0.5rem 1.5rem",
              background: "#334155",
              color: "#f4f7fb",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}