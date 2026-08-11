import type { FieldProps } from "@rjsf/utils";
import { useInitialAttentionCue } from "../../../../../Utility/UI";
import { ScriptEventRenderer, getScriptEventDefinition, isSupportedScriptEvent } from "../../ScriptEvents";
import "./scriptEventField.css";

export function ScriptEventField(props: FieldProps) {
    const { disabled, formData, readonly, registry, uiSchema } = props;
    const { targetRef, isAttentionActive } = useInitialAttentionCue<HTMLDivElement>({
        persistAnimation: true,
    });
    const { SchemaField } = registry.fields;

    if(!isSupportedScriptEvent(formData)) {
        const fallbackUiSchema = { ...(uiSchema ?? {}) };
        delete fallbackUiSchema["ui:field"];
        return (
            <SchemaField
                {...props}
                uiSchema={fallbackUiSchema}
            />
        );
    }

    const shouldHighlight = !!getScriptEventDefinition(formData).highlight;
    const className = shouldHighlight
        ? `script-event-attention${isAttentionActive ? " is-active" : ""}`
        : undefined;

    return (
        <div
            ref={shouldHighlight ? targetRef : undefined}
            className={className}
        >
            <ScriptEventRenderer
                event={formData}
                disabled={disabled}
                readonly={readonly}
            />
        </div>
    );
}
