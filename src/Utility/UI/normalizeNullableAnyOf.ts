import type { RJSFSchema } from "@rjsf/utils";

function isSchemaObject(value: unknown): value is Record<string, any> {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeNullableAnyOfNode(schema: unknown): unknown {
    if(Array.isArray(schema)) {
        return schema.map((item) => normalizeNullableAnyOfNode(item));
    }

    if(!isSchemaObject(schema)) {
        return schema;
    }

    const normalized = Object.fromEntries(
        Object.entries(schema).map(([key, value]) => [
            key,
            normalizeNullableAnyOfNode(value),
        ]),
    );

    if(Array.isArray(normalized.anyOf) && normalized.anyOf.length === 2) {
        const nullSchema = normalized.anyOf.find((option) => isSchemaObject(option) && option.type === "null");
        const valueSchema = normalized.anyOf.find((option) => isSchemaObject(option) && option.type !== "null");

        if(isSchemaObject(nullSchema) && isSchemaObject(valueSchema) && typeof valueSchema.type === "string") {
            const { anyOf, ...rest } = normalized;
            return {
                ...rest,
                ...valueSchema,
                type: [valueSchema.type, "null"],
            };
        }
    }

    return normalized;
}

/**
 * Converts simple nullable `anyOf` schemas into nullable JSON Schema type arrays for RJSF.
 *
 * Pydantic emits `list[int] | None` as `anyOf: [{ type: "array", items: { type: "integer" } }, { type: "null" }]`.
 * RJSF renders that as a variant selector, e.g. an unwanted "Server option 1 / Server option 2" dropdown.
 * The equivalent `type: ["array", "null"]` shape keeps the schema nullable while rendering the normal array field.
 */
export function normalizeNullableAnyOf(schema: RJSFSchema): RJSFSchema {
    return normalizeNullableAnyOfNode(schema) as RJSFSchema;
}
