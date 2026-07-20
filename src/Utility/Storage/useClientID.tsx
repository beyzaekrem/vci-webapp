import { useLocallyStored } from "./useLocallyStored";

/**
 * Returns a stable, locally stored client identifier.
 * @returns Client ID string persisted in localStorage.
 */
export function useClientID() {
    const [clientID, setClientID] = useLocallyStored<string>("clientID", Math.random().toString(36).substring(2, 15));
    return clientID;
}
