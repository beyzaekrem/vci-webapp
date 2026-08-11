/**
 * Provides a singleton instance of the VciAutomation class.
 * Exports init and get functions for the singleton instance.
 * @packageDocumentation
 */

import { createStoredSingleton } from "../../Utility/Storage";
import { InterceptorConnection } from "../interceptor";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";

export type ScriptInfo = {
    id: string;
    name: string;
    description?: string;
};

export type ScriptSchemaResponse = {
    schema: RJSFSchema;
    uiSchema?: UiSchema;
};


class VCIAutomation {
    socket: InterceptorConnection;

    constructor(socket: InterceptorConnection) {
        this.socket = socket;
    }

    getAvailableScripts() {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "SCRIPT_OVERVIEW",
            PAYLOAD: [],
        }).then((response) => {
            const scripts = response.PAYLOAD[0].scripts as ScriptInfo[];
            return scripts;
        });
    }

    get_json_schema_for_script(scriptName: string) {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "GET_SCRIPT_SCHEMA",
            PAYLOAD: [{ script_name: scriptName }],
        }).then((response) => {
            return response.PAYLOAD[0] as ScriptSchemaResponse;
        });
    }

    run_script(scriptName: string, runnerId: string, args?: any) {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "RUN_SCRIPT",
            PAYLOAD: [{ script_name: scriptName, runner_id: runnerId, arguments: args }]
        });
    }

    stop_script(runnerId: string) {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "STOP_SCRIPT",
            PAYLOAD: [{ runner_id: runnerId }]
        });
    }

    private subscribe_to_script(runnerId: string) {
        this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "SUBSCRIBE_TO_SCRIPT",
            PAYLOAD: [{ runner_id: runnerId }]
        });
    }

    add_listener_output(runnerId: string, listener: (message: any) => void) {
        const handler = (message: any) => {
            if(message.PATH === "OUTPUT_UPDATE" && message.PAYLOAD[0].runner_id === runnerId) {
                listener(message.PAYLOAD[0]);
            }
        };
        this.socket.addListener(handler);
        this.subscribe_to_script(runnerId) //TODO make send only execute once connection is open
        return () => this.socket.removeListener(handler);
    }

    send_script_event_response(runnerId: string, eventId: string, eventResponse: any) {
        this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "SCRIPT_EVENT_RESPONSE",
            PAYLOAD: [{
                runner_id: runnerId,
                event_id: eventId,
                event_response: eventResponse,
            }],
        });
    }
}

export type VCIAutomationConfig = { address: string; port?: number; route?: string };

export const vciAutomationSingleton = createStoredSingleton<VCIAutomation, VCIAutomationConfig>(
    (config) => {
        const { address, port = 2525, route } = config;
        const url = `ws://${address}:${port}${route ? "/" + route : ""}`;
        console.log("Initializing VciAutomation with config:", config, "and URL:", url);
        const socket = new InterceptorConnection(url)
        return new VCIAutomation(socket);
    }
);

export const initVCI = vciAutomationSingleton.init;
export const getVCI = vciAutomationSingleton.get;
export const useVCIConfig = vciAutomationSingleton.useLocallyStoredConfig;
export const useVCIAddresses = useVCIConfig;
export const reloadVCI = vciAutomationSingleton.reload;
