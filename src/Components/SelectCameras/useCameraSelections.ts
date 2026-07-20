import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useLocallyStored } from "../../Utility/Storage";
import { useStored } from "../../Utility/Storage";


/**
 * Data structure representing a selected camera.
 */
export interface CameraSelection {
    server: number;
    camera: number;
}

/**
 * Unified hook to obtain the currently selected camera(s) as an array.
 * The storage mechanism is chosen via the options.
 *
 * @param options.storage - Either "url" or "local".
 * @param options.selectionKey - The key name to use (defaults to "cameras").
 */
export function useCameraSelections(
    options: { storage: "url" | "local"; selectionKey?: string; } = {
        storage: "url",
        selectionKey: "cameras",
    }): [CameraSelection[], (selections: CameraSelection[]) => void] {
    const key = options.selectionKey || "cameras";
    if(options.storage === "url") {
        return useCameraSelectionsURL(key);
    } else {
        return useCameraSelectionsLocal(key);
    }
}

/**
 * Helper to parse a string like "0-1,1-2" into an array of CameraSelection objects.
 */
export const parseCameraSelections = (param: string | null): CameraSelection[] => {
    if(!param) return [];
    return param.split(",").map((pair) => {
        const [serverStr, cameraStr] = pair.split("-");
        return { server: parseInt(serverStr, 10), camera: parseInt(cameraStr, 10) };
    });
};

/**
 * Hook for URL-based camera selections.
 * Always encodes the selection as a comma-separated list (even if there is only one).
 */
function useCameraSelectionsURL(
    selectionKey: string = "cameras"
): [CameraSelection[], (selections: CameraSelection[]) => void] {
    const [searchParams, setSearchParams] = useSearchParams();
    const initial = parseCameraSelections(searchParams.get(selectionKey));
    const defaultSelection = [] as CameraSelection[];
    const [selections, setSelections] = useState<CameraSelection[]>(
        initial.length > 0 ? initial : defaultSelection
    );

    useEffect(() => {
        const value = selections.map((sel) => `${sel.server}-${sel.camera}`).join(",");
        const newParams = new URLSearchParams(searchParams);
        newParams.set(selectionKey, value);
        setSearchParams(newParams, { replace: true });
    }, [selections, selectionKey, searchParams, setSearchParams]);

    return [selections, setSelections];
}

/**
 * Hook for local-storage–based camera selections.
 * The value is always stored as an array.
 */
function useCameraSelectionsLocal(
    selectionKey: string = "cameras"
): [CameraSelection[], (selections: CameraSelection[]) => void] {
    return useLocallyStored<CameraSelection[]>(selectionKey, []);
}

/**
 * A read-only hook that simply returns the current camera selections
 * without writing any default value. For URL storage, it directly parses the
 * current query parameter. For local storage, it returns what’s in storage (or an empty array).
 *
 * Use this hook if you want to “peek” at the current selection without causing
 * an unwanted default (like 0-0) to be written.
 *
 * @param options.storage - "url" or "local"
 * @param options.selectionKey - The key name to use (defaults to "cameras")
 * @returns The current camera selections as an array.
 */

export function useCameraSelectionsReadOnly(
    options: { storage: "url" | "local"; selectionKey?: string; } = {
        storage: "url",
        selectionKey: "cameras",
    }
): CameraSelection[] {
    // Ensure the key is always defined.
    const key = options.selectionKey || "cameras";

    const [stored, setStored] = useStored({
        storage: options.storage,
        key,
        defaultValue: [] as CameraSelection[],
        stringToObject: parseCameraSelections,
    });

    return stored;
}

