import { useState } from "react";
import { ScriptList } from "../Components/VCIAutomation/ScriptList";
import { type ScriptInfo } from "../network/vci-automation";
import { VCIAutomationScript } from "../Components/VCIAutomation/VCIAutomationScript";
import { ServerStatusButton } from "../Components/Config/ServerStatusModal";
import "../Components/VCIAutomation/vciAutomation.css";

export function VCIAutomationPage() {
    const [selectedScript, setSelectedScript] = useState<ScriptInfo | null>(null);

    return (
        <div className="vci-auto-container">
            {/* Header Bar */}
            <header className="vci-auto-header">
                <div className="vci-auto-header-left">
                    <h1 className="vci-auto-title">VCI Automation</h1>
                    <span className="vci-auto-status-pill">
                        <span className="vci-auto-status-dot" />
                        ONLINE
                    </span>
                </div>
                <div className="vci-auto-header-right">
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
