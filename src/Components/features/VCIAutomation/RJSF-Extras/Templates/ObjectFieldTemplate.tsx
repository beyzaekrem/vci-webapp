import { Accordion } from "react-bootstrap";
import type {
    FormContextType,
    ObjectFieldTemplateProps,
    ObjectFieldTemplatePropertyType,
    RJSFSchema,
    StrictRJSFSchema,
    UiSchema,
} from "@rjsf/utils";

type UiGroup = {
    title?: string;
    label?: string;
    name?: string;
    fields?: unknown;
    properties?: unknown;
    children?: unknown;
    elements?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

function getUiGroups<
    T = unknown,
    S extends StrictRJSFSchema = RJSFSchema,
    F extends FormContextType = FormContextType,
>(uiSchema: UiSchema<T, S, F> | undefined): UiGroup[] {
    if(!isRecord(uiSchema)) {
        return [];
    }

    const groups = uiSchema["ui:groups"];
    if(!Array.isArray(groups)) {
        return [];
    }

    return groups.filter(isRecord) as UiGroup[];
}

function getGroupTitle(group: UiGroup, index: number) {
    return group.title ?? group.label ?? group.name ?? `Group ${index + 1}`;
}

function getGroupFieldNames(group: UiGroup): string[] {
    const fieldLists = [group.fields, group.properties, group.children, group.elements];

    for(const fieldList of fieldLists) {
        if(Array.isArray(fieldList)) {
            return fieldList.filter((fieldName): fieldName is string => typeof fieldName === "string");
        }
    }

    return [];
}

function renderProperties(properties: ObjectFieldTemplatePropertyType[]) {
    return properties.map((property) => (
        <div key={property.name}>{property.content}</div>
    ));
}

/**
 * Render properties with required labels marked with a red asterisk.
 */
function renderRequiredProperties(properties: ObjectFieldTemplatePropertyType[]) {
    return properties.map((property) => (
        <div key={property.name} className="vci-required-field">
            {property.content}
        </div>
    ));
}

/**
 * Auto-split: separates required fields (top) from optional fields (accordion).
 * Used when no ui:groups are defined in the uiSchema.
 */
function AutoSplitLayout({
    visibleProperties,
    hiddenProperties,
    requiredFieldNames,
    optionalDataControl,
}: {
    visibleProperties: ObjectFieldTemplatePropertyType[];
    hiddenProperties: ObjectFieldTemplatePropertyType[];
    requiredFieldNames: Set<string>;
    optionalDataControl?: React.ReactNode;
}) {
    const requiredProps = visibleProperties.filter((p) => requiredFieldNames.has(p.name));
    const optionalProps = visibleProperties.filter((p) => !requiredFieldNames.has(p.name));

    return (
        <>
            {renderProperties(hiddenProperties)}

            {/* Required fields always visible at top */}
            {requiredProps.length > 0 && (
                <div className="vci-required-section">
                    {renderRequiredProperties(requiredProps)}
                </div>
            )}

            {/* Optional fields in a collapsed accordion */}
            {optionalProps.length > 0 && (
                <Accordion className="mb-3 vci-optional-accordion">
                    <Accordion.Item eventKey="optional">
                        <Accordion.Header>
                            <span className="vci-optional-accordion-title">
                                ⚙️ Advanced / Optional Settings
                            </span>
                        </Accordion.Header>
                        <Accordion.Body>
                            {renderProperties(optionalProps)}
                        </Accordion.Body>
                    </Accordion.Item>
                </Accordion>
            )}

            {optionalDataControl}
        </>
    );
}

export function ObjectFieldTemplate<
    T = unknown,
    S extends StrictRJSFSchema = RJSFSchema,
    F extends FormContextType = FormContextType,
>(props: ObjectFieldTemplateProps<T, S, F>) {
    /**
     * This template groups properties based on the "ui:groups" property in the uiSchema.
     * Each group is rendered as an Accordion section.
     * 
     * If no ui:groups are defined, it auto-splits properties based on the
     * schema's "required" array: required fields on top, optional fields in a
     * collapsed accordion.
     */
    const {
        className,
        description,
        optionalDataControl,
        properties,
        title,
        uiSchema,
        schema,
    } = props;

    const visibleProperties = properties.filter((property) => !property.hidden);
    const hiddenProperties = properties.filter((property) => property.hidden);
    const uiGroups = getUiGroups(uiSchema);

    // If no ui:groups defined, use auto-split by required/optional
    if (uiGroups.length === 0) {
        const requiredFieldNames = new Set<string>(
            Array.isArray(schema.required) ? (schema.required as string[]) : []
        );

        // Only auto-split if there are both required AND optional fields
        const hasRequired = visibleProperties.some((p) => requiredFieldNames.has(p.name));
        const hasOptional = visibleProperties.some((p) => !requiredFieldNames.has(p.name));

        if (hasRequired && hasOptional) {
            return (
                <fieldset className={className}>
                    {title && <legend>{title}</legend>}
                    {description}
                    <AutoSplitLayout
                        visibleProperties={visibleProperties}
                        hiddenProperties={hiddenProperties}
                        requiredFieldNames={requiredFieldNames}
                        optionalDataControl={optionalDataControl}
                    />
                </fieldset>
            );
        }
    }

    // Original ui:groups-based layout
    const groupedPropertyNames = new Set<string>();

    const groupedSections = uiGroups.map((group, index) => {
        const fieldNames = new Set(getGroupFieldNames(group));
        const groupProperties = visibleProperties.filter((property) => fieldNames.has(property.name));

        groupProperties.forEach((property) => groupedPropertyNames.add(property.name));

        return {
            eventKey: String(index),
            properties: groupProperties,
            title: getGroupTitle(group, index),
        };
    }).filter((group) => group.properties.length > 0);

    const ungroupedProperties = visibleProperties.filter(
        (property) => !groupedPropertyNames.has(property.name),
    );

    return (
        <fieldset className={className}>
            {title && <legend>{title}</legend>}
            {description}
            {renderProperties(hiddenProperties)}
            {groupedSections.map((group) => (
                <Accordion key={group.eventKey} defaultActiveKey={group.eventKey} className="mb-3">
                    <Accordion.Item eventKey={group.eventKey}>
                        <Accordion.Header>{group.title}</Accordion.Header>
                        <Accordion.Body>
                            {renderProperties(group.properties)}
                        </Accordion.Body>
                    </Accordion.Item>
                </Accordion>
            ))}
            {renderProperties(ungroupedProperties)}
            {optionalDataControl}
        </fieldset>
    );
}
