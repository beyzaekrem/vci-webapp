import { getScriptEventDefinition, type ScriptEventRenderProps } from "./ScriptEventRegistry";

export function ScriptEventRenderer(props: ScriptEventRenderProps) {
    return getScriptEventDefinition(props.event).render(props);
}
