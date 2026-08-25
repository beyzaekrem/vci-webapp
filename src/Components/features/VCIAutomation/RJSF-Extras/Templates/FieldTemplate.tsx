import type { FieldTemplateProps } from "@rjsf/utils";

/**
 * Custom FieldTemplate for RJSF forms.
 * Appends a prominent red notice under required input fields.
 */
export function FieldTemplate(props: FieldTemplateProps) {
    const {
        id,
        classNames,
        label,
        required,
        children,
        errors,
        help,
        description,
        hidden,
        displayLabel,
    } = props;

    if (hidden) {
        return <div style={{ display: "none" }}>{children}</div>;
    }

    return (
        <div className={`${classNames || ""} ${required ? "vci-required-field" : ""}`}>
            {displayLabel && label && (
                <label htmlFor={id} className="control-label">
                    {label}
                </label>
            )}
            {children}

            {/* Clean Professional Red Notice for Required Fields */}
            {required && (
                <div className="vci-required-notice-text">
                    Mandatory: This field is required and must be filled.
                </div>
            )}

            {description}
            {help}
            {errors}
        </div>
    );
}
