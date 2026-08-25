import Settings from "../Components/features/Config/Settings.tsx";
import { ServerStatusButton, HelpButton } from "../Components/shared/ServerStatusModal";
import { useSidebar } from "../Components/shared/Sidebar/Sidebar";
import { Menu } from "lucide-react";

export function ConfigPage() {
  const { openSidebar } = useSidebar();
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
          <h1 className="vci-header-title">Settings</h1>
        </div>
        <div className="vci-header-right">
          <HelpButton />
          <ServerStatusButton />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="cfg-main-area" style={{ flex: 1, padding: "24px 28px", minHeight: 0, overflow: "auto" }}>
        <Settings />
      </main>
    </div>
  );
}

