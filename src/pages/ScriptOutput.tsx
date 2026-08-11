import { useParams } from "react-router-dom";
import { ScriptInteractions } from "../Components/features/VCIAutomation/ScriptInteractions";
import { RenderedScriptOutput } from "../Components/features/VCIAutomation/RenderedScriptOutput";
import { ScriptLogs } from "../Components/features/VCIAutomation/ScriptLogs";
import { ServerStatusButton } from "../Components/shared/ServerStatusModal";

export function ScriptOutputPage() {
    const { runnerId } = useParams<{ runnerId: string }>();

    if(!runnerId) {
        return (
            <div className="ps-content-wrapper">
                <header className="ps-header-bar">
                    <h1 className="ps-header-title">Script Output</h1>
                    <ServerStatusButton />
                </header>
                <div style={{ padding: 24, color: "#64748b" }}>Missing runner ID parameter.</div>
            </div>
        );
    }

    return (
        <div className="ps-content-wrapper">
            {/* Header Bar */}
            <header className="ps-header-bar">
                <h1 className="ps-header-title">Script Execution Output</h1>
                <ServerStatusButton />
            </header>

            {/* Main Area */}
            <main style={{ flex: 1, padding: "24px 28px", minHeight: 0, overflow: "auto" }}>
                <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", flexDirection: "column", gap: "20px" }}>
                    <ScriptLogs runnerId={runnerId} />
                    <RenderedScriptOutput runnerId={runnerId} />
                    <ScriptInteractions runnerId={runnerId} />
                </div>
            </main>
        </div>
    );
}

