/**
 * Connection to trigger box for external camera triggering.
 * @packageDocumentation
 */

/**
 * Allows communication with the trigger box to control external triggering of cameras.
 * By default, tries to connect to trigger box at 10.3.10.20:8080
 */
export class TriggerBox {
    /**
     * Creates a TriggerBox client.
     * @param url Base URL for the trigger box HTTP API.
     */
    constructor(public url: string = "http://10.3.10.20:8080") { }

    /**
     * Set trigger box state.
     * Call help() to see available states.
     * @param state The state string to send to the trigger box.
     * @returns A promise resolving to the fetch response.
     */
    setState(state: string): Promise<Response> {
        return fetch(`${this.url}/${state}`);
    }

    /**
     * Set trigger box state, but ignore errors (e.g. if trigger box is not reachable).
     * @param state The state string to send to the trigger box.
     * @returns A promise that resolves when the request finishes or is ignored on error.
     */
    setStateIfAvailable(state: string): Promise<Response | void> {
        return this.setState(state).catch((e) => {
            console.warn("Trigger box not reachable:", e);
        });
    }

    /**
     * Get help from trigger box (available states).
     * @returns A promise that resolves after logging the help response.
     */
    help(): Promise<void> {
        return fetch(`${this.url}/help`).then(response => response.text()).then(data => {
            console.log("Trigger box response:", data);
        });
    }
}

/**
 * Singleton instance of TriggerBox for easy access.
 */
export const triggerBox = new TriggerBox();
