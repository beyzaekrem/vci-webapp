import type { ArrayFieldTemplateProps, FormContextType, RJSFSchema, StrictRJSFSchema } from "@rjsf/utils";
import { buttonId, getTemplate, getUiOptions } from "@rjsf/utils";

export function ArrayFieldTemplate<
    T = any,
    S extends StrictRJSFSchema = RJSFSchema,
    F extends FormContextType = any,
>(props: ArrayFieldTemplateProps<T, S, F>) {
    const {
        canAdd,
        disabled,
        fieldPathId,
        items,
        onAddClick,
        optionalDataControl,
        readonly,
        registry,
        required,
        schema,
        title,
        uiSchema,
    } = props;
    const uiOptions = getUiOptions<T, S, F>(uiSchema);
    const ArrayFieldDescriptionTemplate = getTemplate<"ArrayFieldDescriptionTemplate", T, S, F>(
        "ArrayFieldDescriptionTemplate",
        registry,
        uiOptions,
    );
    const ArrayFieldTitleTemplate = getTemplate<"ArrayFieldTitleTemplate", T, S, F>(
        "ArrayFieldTitleTemplate",
        registry,
        uiOptions,
    );
    const {
        ButtonTemplates: { AddButton },
    } = registry.templates;
    const showOptionalDataControlInTitle = !readonly && !disabled;

    return (
        <div>
            <ArrayFieldTitleTemplate
                fieldPathId={fieldPathId}
                title={uiOptions.title || title}
                schema={schema}
                uiSchema={uiSchema}
                required={required}
                registry={registry}
                optionalDataControl={showOptionalDataControlInTitle ? optionalDataControl : undefined}
            />
            <ArrayFieldDescriptionTemplate
                fieldPathId={fieldPathId}
                description={uiOptions.description || schema.description}
                schema={schema}
                uiSchema={uiSchema}
                registry={registry}
            />
            {!showOptionalDataControlInTitle ? optionalDataControl : undefined}
            {items}
            {canAdd && (
                <div className="mt-2">
                    <div style={{ width: "fit-content" }}>
                        <AddButton
                            id={buttonId(fieldPathId, "add")}
                            className="rjsf-array-item-add"
                            onClick={onAddClick}
                            disabled={disabled || readonly}
                            uiSchema={uiSchema}
                            registry={registry}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
