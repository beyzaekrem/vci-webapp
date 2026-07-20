import { useParams } from "react-router-dom";
import { ScriptInteractions } from "../Components/VCIAutomation/ScriptInteractions";
import { RenderedScriptOutput } from "../Components/VCIAutomation/RenderedScriptOutput";
import { ScriptLogs } from "../Components/VCIAutomation/ScriptLogs";

export function ScriptOutputPage() {
    const { runnerId } = useParams<{ runnerId: string }>();

    if(!runnerId) {
        return <div className="m-3">Missing runner id.</div>;
    }

    return (
        <div
            className="d-flex justify-content-center"
            style={{ width: "100%" }}
        >
            <div style={{ width: "100%", maxWidth: 1400, minWidth: 0, margin: 15 }}>
                <ScriptLogs runnerId={runnerId} />
                <RenderedScriptOutput runnerId={runnerId} />
                <ScriptInteractions runnerId={runnerId} />
            </div>
        </div>
    );
}
