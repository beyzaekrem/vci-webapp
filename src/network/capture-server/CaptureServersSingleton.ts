/**
 * Provides a singleton instance of the CaptureServers class, which manages the WebSocket connections to multiple capture servers.
 * Exports init and get functions for the singleton instance.
 * @packageDocumentation
 */

import { CaptureServers, CaptureServer } from "./CaptureServer";
import { createStoredSingleton } from "../../Utility/Storage";

type CaptureServerConfig = { addresses: string[], port?: number, route?: string };

export const captureServersSingleton = createStoredSingleton<CaptureServers, CaptureServerConfig>(
    (config) => {
        console.log("Initializing CaptureServers with config:", config);
        return new CaptureServers(
            config.addresses.map((addr) => new CaptureServer(`ws://${addr}:${config.port || 2443}${config.route || "/websocket"}`))
        )

    }
);

export const initCaptureServers = captureServersSingleton.init;
export const getServers = captureServersSingleton.get;
export const useServerAddresses = captureServersSingleton.useLocallyStoredConfig;
export const reloadCaptureServers = captureServersSingleton.reload;
