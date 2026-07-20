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

export function ObjectFieldTemplate<
    T = unknown,
    S extends StrictRJSFSchema = RJSFSchema,
    F extends FormContextType = FormContextType,
>(props: ObjectFieldTemplateProps<T, S, F>) {
    /**
     * This template groups properties based (only) on the "ui:groups" property in the uiSchema.
     * Each group is rendered as an Accordion section.
     * Properties that are not included in any group are rendered at the end,
     * outside of the Accordion.
     */
    const {
        className,
        description,
        optionalDataControl,
        properties,
        title,
        uiSchema,
    } = props;

    const visibleProperties = properties.filter((property) => !property.hidden);
    const hiddenProperties = properties.filter((property) => property.hidden);
    const uiGroups = getUiGroups(uiSchema);
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
