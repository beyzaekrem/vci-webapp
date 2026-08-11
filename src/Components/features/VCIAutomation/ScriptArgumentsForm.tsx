import Form from "@rjsf/react-bootstrap";
import type { IChangeEvent } from "@rjsf/core";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";
import { useCallback, useEffect, useState } from "react";
import { getVCI, type ScriptSchemaResponse } from "../../../network/vci-automation";
import { normalizeNullableAnyOf } from "../../../Utility/UI";
import { templates } from "./RJSF-Extras";
import { validator } from "./validator";

export function ScriptArgumentsForm({
    scriptName,
    onSubmit,
}: {
    scriptName: string;
    onSubmit?: (formData: unknown) => void;
}) {
    const [schema, setSchema] = useState<RJSFSchema | null>(null);
    const [uiSchema, setUiSchema] = useState<UiSchema | undefined>(undefined);
    const [formData, setFormData] = useState<unknown>({});
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadSchema = useCallback(() => {
        setIsLoading(true);
        setError(null);

        getVCI().get_json_schema_for_script(scriptName)
            .then((scriptSchema: ScriptSchemaResponse) => {
                const normalizedSchema = normalizeNullableAnyOf(scriptSchema.schema);
                setSchema(normalizedSchema);
                setUiSchema(scriptSchema.uiSchema);
                setFormData({});
            })
            .catch((reason) => {
                console.error("Failed to load script schema:", reason);
                setError(reason instanceof Error ? reason.message : String(reason));
            })
            .finally(() => {
                setIsLoading(false);
            });
    }, [scriptName]);

    useEffect(() => {
        const timeoutId = setTimeout(() => {
            loadSchema();
        }, 200);
        return () => clearTimeout(timeoutId);
    }, [loadSchema]);

    return (
        <div className="mt-4 text-start" style={{ maxWidth: "100%", minWidth: 0 }}>
            {isLoading && <div>Loading schema...</div>}
            {error && <pre style={{ color: "red" }}>{error}</pre>}
            {schema && (
                <Form
                    schema={schema}
                    uiSchema={uiSchema}
                    templates={templates}
                    validator={validator}
                    formData={formData}
                    onChange={(event: IChangeEvent) => setFormData(event.formData)}
                    onSubmit={(event: IChangeEvent) => {
                        onSubmit?.(event.formData);
                    }}
                />
            )}
        </div>
    );
}
