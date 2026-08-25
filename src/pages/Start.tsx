import { useEffect, useRef } from "react";
import { ServerOverview } from "../Components/shared/ServerOverview.tsx";
import { ServerStatusButton, HelpButton } from "../Components/shared/ServerStatusModal";
import { useSidebar } from "../Components/shared/Sidebar/Sidebar";
import { Menu } from "lucide-react";

export function StartPage() {
  const { openSidebar } = useSidebar();
  const mainRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, []);

  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar vci-unified-header">
        <div className="vci-header-left">
          <button
            type="button"
            className="vci-header-hamburger-btn"
            onClick={openSidebar}
            title="Open Navigation Menu"
          >
            <Menu size={18} />
          </button>
          <h1 className="vci-header-title">Server Status</h1>
        </div>
        <div className="vci-header-right">
          <HelpButton />
          <ServerStatusButton />
        </div>
      </header>

      {/* Main Content Card Container - Centered in Viewport */}
      <main ref={mainRef} className="start-main-container" style={{ flex: 1, padding: "32px", display: "flex", justifyContent: "center", alignItems: "flex-start", minHeight: 0, overflow: "auto" }}>
        <div className="start-card-container" style={{
          width: "100%",
          maxWidth: "850px",
          backgroundColor: "var(--vci-card-bg)",
          borderRadius: "12px",
          border: "1px solid var(--vci-card-border)",
          padding: "28px 32px",
          boxShadow: "var(--vci-card-shadow)",
          textAlign: "center",
          transition: "background-color 0.25s ease, border-color 0.25s ease"
        }}>
          <ServerOverview />
        </div>
      </main>
    </div>
  );
}
