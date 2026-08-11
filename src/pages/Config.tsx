import Settings from "../Components/features/Config/Settings.tsx";
import { ServerStatusButton } from "../Components/shared/ServerStatusModal";

export function ConfigPage() {
  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar">
        <h1 className="ps-header-title">Settings</h1>
        <ServerStatusButton />
      </header>

      {/* Main Content Area */}
      <main className="cfg-main-area" style={{ flex: 1, padding: "24px 28px", minHeight: 0, overflow: "auto" }}>
        <Settings />
      </main>
    </div>
  );
}

