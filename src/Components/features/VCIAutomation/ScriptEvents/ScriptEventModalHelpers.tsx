import type { AlertModalProps } from "../../../../Utility/UI";
import type { ScriptEvent } from "../../../../network/vci-automation";
import {
    getScriptEventDefinition,
    isScriptInteractionResponse,
    isSupportedScriptEvent,
} from "./ScriptEventRegistry";

const nonInteractionEventTypes = new Set(["LOG"]);

export function isNonInteractionScriptEvent(event: ScriptEvent) {
    return nonInteractionEventTypes.has(event.type);
}

export function getScriptEventModalProps(
    event: ScriptEvent,
    onComplete: () => void,
): Omit<AlertModalProps, "show" | "setShow"> | null {
    if(!isSupportedScriptEvent(event)) {
        return null;
    }

    return getScriptEventDefinition(event).getModalProps?.(event, onComplete) ?? null;
}

export { isScriptInteractionResponse, isSupportedScriptEvent };
