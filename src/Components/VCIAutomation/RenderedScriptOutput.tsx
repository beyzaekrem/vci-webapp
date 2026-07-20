import Form from "@rjsf/react-bootstrap";
import type { RJSFSchema } from "@rjsf/utils";
import { useEffect, useState } from "react";
import { getVCI } from "../../network/vci-automation";
import { normalizeNullableAnyOf } from "../../Utility/UI";
import { validator } from "./validator";
import { fields, widgets } from "./RJSF-Extras";

export function RenderedScriptOutput({ runnerId }: { runnerId: string }) {
    const [output, setOutput] = useState<unknown>(null);
    const [outputJsonSchema, setOutputJsonSchema] = useState<RJSFSchema | null>(null);
    const [uiSchema, setUiSchema] = useState<Record<string, unknown> | null>(null);

    useEffect(() => {
        const removeListener = getVCI().add_listener_output(runnerId, (message) => {
            setOutput(message.output);
            setOutputJsonSchema(normalizeNullableAnyOf(message.output_json_schema));
            let uiSchema = message.output_ui_schema as Record<string, unknown> | undefined;
            if(!uiSchema) {
                uiSchema = {};
            }
            uiSchema["ui:submitButtonOptions"] = { norender: true };
            setUiSchema(uiSchema);
        });
        return () => {
            removeListener();
        };
    }, [runnerId]);

    if(!output || !outputJsonSchema) {
        return <div>No output yet</div>;
    }

    return (
        <div>
            <Form
                schema={outputJsonSchema}
                formData={output}
                validator={validator}
                widgets={widgets}
                fields={fields}
                uiSchema={uiSchema as Record<string, unknown>}
                onChange={() => { }}
            />
        </div>
    );
}

export function DebugScriptOutput({ runnerId }: { runnerId: string }) {
    const [messages, setMessages] = useState<unknown[]>([]);

    useEffect(() => {
        const removeListener = getVCI().add_listener_output(runnerId, (message) => {
            const fullHistory = message.full_event_history
            setMessages(fullHistory)
        });
        return () => {
            removeListener();
        };
    }, [runnerId]);

    return (
        <div>
            <h3>Output</h3>
            {messages.map((msg, index) => (
                <pre key={index}>{JSON.stringify(msg, null, 2)}</pre>
            ))}
        </div>
    );
}
