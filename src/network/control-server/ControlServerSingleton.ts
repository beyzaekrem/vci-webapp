/**
 * Provides a singleton instance of the ControlServer class, which manages the WebSocket connection to the control server.
 * Exports init and get functions for the singleton instance.
 * @packageDocumentation
 */
import { isValidAddress } from "../interceptor"
import { createStoredSingleton } from "../../Utility/Storage";
import { ControlServer } from "./ControlServer";

export type ControlServerConfig = {
    address: string;
    port?: number;
    route?: string;
};

const controlServerSingleton = createStoredSingleton<ControlServer, ControlServerConfig>(
    (config) => {
        if(!isValidAddress(config.address)) throw new Error(`Invalid control server address: ${config.address}`);
        return new ControlServer(`ws://${config.address}:${config.port || 5555}${config.route || "/websocket"}`);
    }
);

export const initControlServer = controlServerSingleton.init;
export const getControlServer = controlServerSingleton.get;
export const useControlServerConfig = controlServerSingleton.useLocallyStoredConfig;
export const reloadControlServer = controlServerSingleton.reload;

// Backwards-compatible helper for callers that only need the address field.
export function useControlServerAddress(): [string, (value: string) => void] {
    const [config, setConfig] = useControlServerConfig();
    return [config.address, (address: string) => setConfig({ ...config, address })];
}