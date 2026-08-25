import { getVCI, ScriptInfo } from "../../../network/vci-automation";
import { ScriptArgumentsForm } from "./ScriptArgumentsForm";
import { useLocallyStored } from "../../../Utility/Storage";
import { fullscreenIcon } from "../../shared/Icons";
import { ScriptOutput } from "./ScriptOutput";
import { Play, Square } from "lucide-react";

export function VCIAutomationScript({ script }: { script: ScriptInfo }) {
    const [runnerId] = useLocallyStored<string>(`vci-automation-runner-${script.id}`, `runner-${Math.random().toString(16).slice(2)}`);

    const handleExecuteClick = () => {
        const formElem = document.querySelector(".vci-script-config-card form") as HTMLFormElement;
        if (formElem) {
            formElem.requestSubmit();
        } else {
            getVCI().run_script(script.id, runnerId, {});
        }
    };

    return (
        <>
            {/* Center Column: Configuration Form & Execution Controls */}
            <div className="vci-script-config-card">
                <div className="vci-config-header">
                    <h2 className="vci-config-title">{script.name}</h2>
                    <p className="vci-config-subtitle">
                        {script.description || "Configure exposure profiles and target servers for background image acquisition"}
                    </p>
                </div>

                <ScriptArgumentsForm
                    scriptName={script.id}
                    onSubmit={(formData) => {
                        getVCI().run_script(script.id, runnerId, formData);
                    }}
                />

                <div className="vci-script-actions" style={{ marginTop: "24px", display: "flex", flexDirection: "column", gap: "10px" }}>
                    <button
                        type="button"
                        className="vci-btn-execute"
                        onClick={handleExecuteClick}
                    >
                        <Play size={15} fill="currentColor" />
                        <span>Execute Script</span>
                    </button>

                    <button
                        type="button"
                        className="vci-btn-stop"
                        onClick={() => {
                            getVCI().stop_script(runnerId);
                        }}
                    >
                        <Square size={14} fill="currentColor" />
                        <span>Stop Script Execution</span>
                    </button>
                </div>
            </div>

            {/* Right Column: Execution Logs Terminal */}
            <div className="vci-logs-card">
                <div className="vci-logs-header">
                    <span className="vci-logs-header-badge">EXECUTION LOGS</span>
                    <a
                        href={`/#/vci-automation/script_output/${runnerId}`}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-sm btn-outline-light"
                        style={{ fontSize: "11px", opacity: 0.8 }}
                    >
                        {fullscreenIcon} Fullscreen
                    </a>
                </div>

                <ScriptOutput runnerId={runnerId} />
            </div>
        </>
    );
}
