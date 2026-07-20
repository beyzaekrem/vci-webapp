import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useLocallyStored } from "./useLocallyStored";

export interface StoredHookOptions<T> {
    /** Where to persist the value. */
    storage: "url" | "local";
    /** Key used for the URL query string or localStorage. */
    key: string;
    /** Value used when nothing is stored yet. */
    defaultValue: T;
    /** Parses a string representation into a typed value. */
    stringToObject: (str: string) => T;
    /** Converts the value into a string for storage. */
    objectToString?: (obj: T) => string;
}

/**
 * Reads a value from URL search params or localStorage and provides a setter.
 * @param options Configuration for storage location and serialization.
 * @returns Tuple of current value and a setter that persists the value.
 */
export function useStored<T>(options: StoredHookOptions<T>): [T, (newValue: T) => void] {
    const { key, defaultValue, stringToObject, objectToString } = options;

    // Always call hooks unconditionally
    const [searchParams, setSearchParams] = useSearchParams();
    const [localValue, setLocalValue] = useLocallyStored<T>(key, defaultValue);

    // Compute the URL value unconditionally
    const valueFromUrl = searchParams.get(key);
    const parsedValue = useMemo(() => {
        return valueFromUrl ? stringToObject(valueFromUrl) : defaultValue;
    }, [valueFromUrl, defaultValue, stringToObject]);

    // Choose which pair to return based on the storage option.
    if(options.storage === "url") {
        const setValue = (newValue: T) => {
            const newParams = new URLSearchParams(searchParams);
            const newValueString = objectToString ? objectToString(newValue) : String(newValue);
            newParams.set(key, newValueString);
            setSearchParams(newParams, { replace: true });
        };
        return [parsedValue, setValue];
    } else {
        return [localValue, setLocalValue];
    }
}
