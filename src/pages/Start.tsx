import { ServerOverview } from "../Components/ServerOverview.tsx";
import { ServerStatusButton } from "../Components/Config/ServerStatusModal";

export function StartPage() {
  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar">
        <h1 className="ps-header-title">Server Status</h1>
        <ServerStatusButton />
      </header>

      {/* Main Content Card Container - Centered in Viewport */}
      <main style={{ flex: 1, padding: "32px", display: "flex", justifyContent: "center", alignItems: "flex-start", minHeight: 0, overflow: "auto" }}>
        <div style={{
          width: "100%",
          maxWidth: "850px",
          backgroundColor: "#ffffff",
          borderRadius: "12px",
          border: "1px solid #e2e8f0",
          padding: "28px 32px",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
          textAlign: "center"
        }}>
          <ServerOverview />
        </div>
      </main>
    </div>
  );
}
