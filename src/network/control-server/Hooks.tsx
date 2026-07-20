/**
 * React hooks for querying control server state and camera positions.
 * @packageDocumentation
 */
import { useState, useEffect } from "react";
import { getControlServer } from "./ControlServerSingleton";


/**
 * Hook to fetch the control server status once on mount.
 * @returns The status payload or null while loading.
 */
export function useControlServerStatus(): any {
    const [status, setStatus] = useState(null);
    useEffect(() => {
        getControlServer()
            .getStatus()
            .then((status) => {
                setStatus(status);
            });
    }, []);
    return status;
}

/**
 * Hook to fetch camera positions once on mount.
 * @returns The positions payload or null while loading.
 */
export function useCameraPositions(): any {
    const [positions, setPositions] = useState(null);
    useEffect(() => {
        getControlServer()
            .getCameraPositions()
            .then((positions) => {
                setPositions(positions);
            });
    }, []);
    return positions;
}
