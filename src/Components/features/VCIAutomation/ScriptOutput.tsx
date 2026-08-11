import { RenderedScriptOutput } from "./RenderedScriptOutput";
import { ScriptInteractions } from "./ScriptInteractions";
import { ScriptLogs } from "./ScriptLogs";

export function ScriptOutput({ runnerId }: { runnerId: string }) {
    return <>
        <ScriptLogs runnerId={runnerId} />
        <RenderedScriptOutput runnerId={runnerId} />
        <ScriptInteractions runnerId={runnerId} />
    </>
}