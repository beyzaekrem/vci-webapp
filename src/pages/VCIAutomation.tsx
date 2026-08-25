import { useState } from "react";
import { ScriptList } from "../Components/features/VCIAutomation/ScriptList";
import { type ScriptInfo } from "../network/vci-automation";
import { VCIAutomationScript } from "../Components/features/VCIAutomation/VCIAutomationScript";
import { ServerStatusButton, HelpButton } from "../Components/shared/ServerStatusModal";
import { useSidebar } from "../Components/shared/Sidebar/Sidebar";
import { Menu } from "lucide-react";
import "../Components/features/VCIAutomation/vciAutomation.css";

export function VCIAutomationPage() {
    const { openSidebar } = useSidebar();
    const [selectedScript, setSelectedScript] = useState<ScriptInfo | null>(null);

    return (
        <div className="vci-auto-container">
            {/* Header Bar */}
            <header className="ps-header-bar vci-auto-header">
                <div className="vci-auto-header-left">
                    <button
                        type="button"
                        className="vci-header-hamburger-btn"
                        onClick={openSidebar}
                        title="Open Navigation Menu"
                    >
                        <Menu size={18} />
                    </button>
                    <h1 className="ps-header-title vci-auto-title">VCI Automation</h1>
                    <span className="vci-auto-status-pill">
                        <span className="vci-auto-status-dot" />
                        ONLINE
                    </span>
                </div>
                <div className="vci-auto-header-right" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <HelpButton />
                    <ServerStatusButton />
                </div>
            </header>

            {/* Main 3-Column Layout */}
            <div className="vci-auto-layout">
                {/* Left Column: Scripts List */}
                <div className="vci-script-list-card">
                    <ScriptList onSelectScript={setSelectedScript} />
                </div>

                {/* Center & Right Columns: Form & Logs */}
                {selectedScript ? (
                    <VCIAutomationScript key={selectedScript.id} script={selectedScript} />
                ) : (
                    <div className="vci-script-config-card" style={{ gridColumn: "span 2" }}>
                        <p className="text-muted text-center py-5">Select a script from the left menu to configure and execute.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
