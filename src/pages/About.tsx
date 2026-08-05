import { NoAutomaticRefreshes } from "../Components/WarningPopups.tsx";
import { ButtonWithKey } from "../Utility/KeyBindings";
import { ServerStatusButton } from "../Components/Config/ServerStatusModal";

export function About() {
  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar">
        <h1 className="ps-header-title">About</h1>
        <ServerStatusButton />
      </header>

      {/* Main Content Container */}
      <main style={{ flex: 1, padding: "24px 28px", minHeight: 0, overflow: "auto" }}>
        <div style={{
          maxWidth: "800px",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: "20px"
        }}>
          {/* Card 1: System Overview */}
          <div style={{
            backgroundColor: "#ffffff",
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            padding: "24px 28px",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)"
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
              <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#0f172a", margin: 0 }}>VCI WebApp System</h2>
              <span style={{
                backgroundColor: "#e0f2fe",
                color: "#0369a1",
                fontSize: "11px",
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: "20px",
                letterSpacing: "0.05em"
              }}>
                v1.0.0
              </span>
            </div>
            <p style={{ fontSize: "14px", color: "#475569", lineHeight: "1.6", margin: 0 }}>
              This web application provides an intuitive interface to configure, capture, calibrate, and stream multi-camera video systems in real time within the VCI ecosystem.
            </p>
          </div>

          {/* Card 2: Help & Shortcuts Guide */}
          <div style={{
            backgroundColor: "#ffffff",
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            padding: "24px 28px",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)"
          }}>
            <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a", marginTop: 0, marginBottom: "16px", borderBottom: "1px solid #f1f5f9", paddingBottom: "10px" }}>
              Keyboard Navigation & Help
            </h3>
            <p style={{ fontSize: "14px", color: "#475569", lineHeight: "1.6" }}>
              Press <kbd style={{ backgroundColor: "#f1f5f9", color: "#0f172a", padding: "2px 6px", borderRadius: "4px", border: "1px solid #cbd5e1", fontFamily: "monospace" }}>h</kbd> or click <ButtonWithKey keybinding="h" /> in the navigation menu at any time to open the documentation and list of active keybindings.
            </p>
            <p style={{ fontSize: "14px", color: "#475569", lineHeight: "1.6", margin: 0 }}>
              Hovering over interactive buttons or long-pressing elements will reveal associated shortcut keys in square brackets <b style={{ color: "#0f172a" }}>[]</b> along with contextual action descriptions.
            </p>
          </div>

          {/* Card 3: Warning & System Refreshes */}
          <div style={{
            backgroundColor: "#ffffff",
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            padding: "24px 28px",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)"
          }}>
            <NoAutomaticRefreshes />
          </div>
        </div>
      </main>
    </div>
  );
}
