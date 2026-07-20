/**
 * This module defines the CaptureServer class, which represents a capture server and provides methods
 * to control camera streams, switch modes, adjust zoom, set stream parameters, and manage camera operations.
 * It utilizes the CaptureServerConnection class to communicate with the capture server through a WebSocket connection.
 * The connections are managed as singletons in CaptureServersSingleton.ts and instantiated in main.tsx.
 * They can be accessed throughout the app via the getServers function from CaptureServersSingleton.ts.
 * @packageDocumentation
 */

import { CaptureServerConnection } from "./CaptureServerConnection";
import { Message } from "../interceptor";
import { downloadImage } from "./downloadImage";
import { triggerBox } from "./TriggerBox";


/**
 * Represents a capture server. Uses a CaptureServerConnection to communicate with the server.
 * 
 * It provides methods to control camera streams, switch modes,
 * adjust zoom, set stream parameters, and manage camera operations through a WebSocket connection.
 * 
*/
export class CaptureServer {
    socket: CaptureServerConnection;
    /**
     * Creates a CaptureServer client for the given WebSocket URL.
     * @param url The capture server WebSocket URL.
     */
    constructor(public url: string) {
        this.socket = new CaptureServerConnection(url);
    }

    /**
     * Request a large json with infos about the cameras and system. See CaptureServerConnection.requestAllInfo for more details.
     * The result will be stored in the CaptureServerConnection and can be accessed with this.socket.getCurrentCamToolState().
     */
    getAllInfo(): void {
        this.socket.requestAllInfo();
    }

    /**
     * Get the domain of the capture server.
     * @returns The domain of the capture server (e.g. "localhost" or "192.168.1.1")
     */
    getDomain(): string {
        const url = new URL(this.url);
        return url.hostname;
    }

    /**
     * Get a camera by its ID (number).
     * @param id The ID of the camera to get (0-indexed)
     * @returns A Camera object representing the camera with the given ID
     */
    getCamera(id: number): Camera {
        return new Camera(this, id);
    }

    //Requests for the server
    /**
     * Switch the mode on the capture server.
     * @param mode The mode to switch to, e.g. "livestream", "calibration", "record", "replay", "single"
     * @returns A promise resolving to the server response.
     */
    switchMode(mode: string): Promise<Message> {
        return this.socket.send({
            PATH: "SWITCH_MODE",
            TYPE: 3, // StandardMessage
            PAYLOAD: [
                {
                    mode: mode,
                },
            ],
        })
    }

    /**
     * Set the parameters for a specific livestream.
     * @param stream_id The stream ID to configure.
     * @param streamParameters The parameters object to send.
     * @returns A promise resolving to the server response.
     */
    setStreamParameters(stream_id: string, streamParameters: any): Promise<Message> {
        return this.socket.send({
            PATH: "SET_STREAM_PARAMETERS",
            TYPE: 3, // StandardMessage
            PAYLOAD: [
                {
                    stream_id: stream_id,
                    parameters: streamParameters,
                },
            ],
        });
    }

    /**
     * Zoom in on a specific livestream.
     * @param stream_id The stream ID to zoom.
     */
    zoom_in(stream_id: string): void {
        this.setStreamParameters(stream_id, { zoom_factor_relative: 1 });
    }

    /**
     * Zoom out on a specific livestream.
     * @param stream_id The stream ID to zoom.
     */
    zoom_out(stream_id: string): void {
        this.setStreamParameters(stream_id, { zoom_factor_relative: -1 });
    }

    /**
     * Move the zoom center relative to its current position.
     * @param stream_id The stream ID to modify.
     * @param move The relative delta in pixels.
     */
    moveZoomCenterRel(stream_id: string, move: { x?: number; y?: number; }): void {
        this.setStreamParameters(stream_id, {
            zoom_center_x_relative: move.x || 0,
            zoom_center_y_relative: move.y || 0,
        });
    }

    /**
     * Reset the zoom center to the image center.
     * @param stream_id The stream ID to modify.
     */
    resetZoomCenter(stream_id: string): void {
        this.setStreamParameters(stream_id, {
            reset_zoom_center: true,
        });
    }

    /**
     * Set the zoom center to specific coordinates.
     * @param stream_id The ID of the stream to set the zoom center for.
     * @param newCenter The new center coordinates for the zoom in pixels. the image center is width/2, height/2.
     * (0, 0) is the top-left corner.
     */
    moveZoomCenter(stream_id: string, newCenter: { x?: number; y?: number; }): void {
        this.setStreamParameters(stream_id, {
            zoom_center_x: newCenter.x || 0,
            zoom_center_y: newCenter.y || 0,
        });
    }

    /**
     * Set the zoom factor for a specific livestream.
     * @param stream_id The ID of the stream to set the zoom factor for.
     * @param factor If the zoom factor is 1, one pixel on the displayed image corresponds to one pixel on the camera sensor.
     * If the zoom factor is e.g. 2, one pixel on the displayed image corresponds to 2x2 pixels on the camera sensor (zoomed in).
     */
    setZoomFactor(stream_id: string, factor: number): void {
        this.setStreamParameters(stream_id, { zoom_factor: factor });
    }

    /**
     * Set the client size for a specific livestream. The server will send images of that size.
     * @param stream_id The ID of the stream to set the client size for.
     * @param size The new client size in pixels.
     */
    setClientSize(stream_id: string, size: { width?: number; height?: number; }): void {
        let params = {} as any;
        if(size.width) params["client_width"] = size.width;
        if(size.height) params["client_height"] = size.height;
        this.setStreamParameters(stream_id, params);
    }

    /**
     * Start all cameras.
     * @returns A promise resolving to the server response.
     */
    startCameras(): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "START",
            PAYLOAD: [],
        });
    }

    /**
     * Stop all cameras.
     * @returns A promise resolving to the server response.
     */
    stopCameras(): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "STOP",
            PAYLOAD: [],
        });
    }

    // TODO implement functionality for creating captured videos etc. note that we need to switch to the other mode/ another server-side messagehandler for this

    /**
     * List all recordings on the server. Will switch to "replay" mode first.
     * @returns A promise resolving to the list of recording names.
     */
    listRecordings(): Promise<Array<string>> {
        return this.switchMode("replay").then(() => {
            return this.socket.send({
                TYPE: 3, // StandardMessage
                PATH: "STATUS",
                PAYLOAD: [],
            }).then((response) => {
                const status = response.PAYLOAD[0] as ReplayStatus;
                console.log(status.recording_name);
                return status.available_recordings;
            });
        })
    }

    /**
     * Set the name for the next recording.
     * @param name Recording name to set.
     * @returns A promise resolving to the server response.
     */
    setRecordingName(name: string = Date.now().toString() + "-from-webapp"): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "SET_RECORDING_NAME",
            PAYLOAD: [
                {
                    recording_name: name,
                },
            ],
        })
    }

    /**
     * Start recording.
     * @returns A promise resolving to the server response.
     */
    startRecording(): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "START",
            PAYLOAD: [],
        })
    }

    /**
     * Stop recording.
     * @returns A promise resolving to the server response.
     */
    stopRecording(): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "STOP",
            PAYLOAD: [],
        })
    }

    /**
     * Set capture FPS on the server.
     * @param fps Frames per second.
     * @returns A promise resolving to the server response.
     */
    setFPS(fps: number = 30): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "SET_FPS",
            PAYLOAD: [
                {
                    fps: fps,
                },
            ],
        })
    }

    /**
     * Delete a recording on the server.
     * @param name Recording name to delete.
     * @returns A promise resolving to the server response.
     */
    deleteRecording(name: string): Promise<Message> {
        return this.socket.send({
            TYPE: 3, // StandardMessage
            PATH: "DELETE_RECORDING",
            PAYLOAD: [
                {
                    recording_name: name,
                },
            ],
        })
    }

}

/**
 * Status payload returned in replay mode.
 */
type ReplayStatus = {
    available_recordings: Array<string>
    camera_ids: Array<string>
    mode: string
    num_cameras: number,
    frame_count: number,
    recording_name: string
}

/**
 * Represents a camera connected to the capture server.
 * 
 * The `Camera` class provides methods to control the camera's stream, set parameters and download images.
 */
export class Camera {
    /**
     * Creates a Camera wrapper.
     * @param server The CaptureServer instance.
     * @param id The camera index on the server.
     */
    constructor(
        public server: CaptureServer,
        public id: number
    ) { }

    /**
     * Gets the serial number of the camera at this.id.
     * @returns The serial number string for this camera
     */
    getSerialNumber(): string | undefined {
        return this.server.socket.getCurrentCamToolState()?.serial_numbers.by_index[this.id];
    }

    /**
     * Gets the shorthand for this camera (e.g. C0007 or M0003).
     * @returns The shorthand string for this camera
     */
    getShorthand(): string | undefined {
        return this.server.socket.getCurrentCamToolState()?.serial_numbers.cam_shorthands[this.id]
    }

    /**
     * Set a parameter for this camera.
     * @param paramName The name of the parameter to set.
     * @param value The value to set the parameter to.
     * @returns A promise resolving to the server response.
     */
    setParameter(paramName: string, value: any): Promise<Message> {
        return this.server.socket.send({
            PATH: "SET_PARAMETER",
            TYPE: 3, // StandardMessage
            PAYLOAD: [
                {
                    name: paramName,
                    value: value,
                    camera_id: this.id,
                },
            ],
        })
    }

    /**
     * Set a parameter for this camera incrementally.
     * @param paramName The name of the parameter to set.
     * @param value How much to increment the parameter by.
     * @returns A promise resolving to the server response.
     */
    setParameterIncremental(paramName: string, value: any): Promise<Message> {
        return this.server.socket.send({
            PATH: "SET_PARAMETER_INCREMENTAL",
            TYPE: 3, // StandardMessage
            PAYLOAD: [
                {
                    name: paramName,
                    value: value,
                    camera_id: this.id,
                },
            ],
        });
    }

    /**
     * Download the full resolution image from the camera.
     */
    downloadImage(): void {
        this.server.socket.send(
            {
                PATH: "GET_IMAGE_FULL",
                TYPE: 3, // StandardMessage
                PAYLOAD: [
                    {
                        camera_id: this.id,
                    },
                ],
            }).then((message) => {
                const img = message.PAYLOAD[1] as Uint8Array;
                const filename = `camera_${this.id}_image.jpg`;

                // Convert the image to a blob and download it
                downloadImage(img, filename);
            });
    }

    /**
     * Request a single image from the camera stream. The server will send the next image that is available.
     * @param livestreamId The ID of the livestream to poll the image from.
     * @returns A promise resolving to the image blob and capture time.
     */
    pollImage(livestreamId: string): Promise<{ blob: Blob; capture_time: number; }> {
        return this.server.socket.send(
            {
                PATH: "POLL_LIVESTREAM_IMAGE",
                TYPE: 3, // StandardMessage
                PAYLOAD: [
                    {
                        stream_id: livestreamId,
                        camera_id: this.id,
                    },
                ],
            }).then((message) => {
                if(message.ERROR) {
                    if(message.ERROR === "INTERCEPTOR::PathDoesNotExist") {
                        // switch to livestream mode and try again
                        return this.server.switchMode("livestream").then((m) => {
                            return this.pollImage(livestreamId);
                        });
                    }
                    console.warn("Error polling image:", message.ERROR);
                }
                const img = message.PAYLOAD[1] as Uint8Array;
                const blob = new Blob([img as any], { type: "image/jpeg" }); //TODO make typing correct here
                const capture_time = message.PAYLOAD[0].capture_time;
                return { blob, capture_time };
            })
    }
}

/**
 * Represents a collection of `CaptureServer` instances and provides utility methods
 * for accessing, iterating, and manipulating the servers and their cameras.
 */
export class CaptureServers implements Iterable<CaptureServer> {
    servers: Array<CaptureServer>;

    /**
     * Creates a collection wrapper for capture servers.
     * @param servers The list of CaptureServer instances.
     */
    constructor(servers: Array<CaptureServer>) {
        this.servers = servers;
    }

    /**
     * Get a specific capture server by its index (0-indexed).
     * @param index The server index.
     * @returns The CaptureServer instance at that index.
     */
    getServer(index: number): CaptureServer {
        return this.servers[index];
    }

    /**
     * Iterate over capture servers in this collection.
     * @returns An iterator over CaptureServer instances.
     */
    [Symbol.iterator](): Iterator<CaptureServer> {
        let index = 0;
        const servers = this.servers;

        return {
            next(): IteratorResult<CaptureServer> {
                if(index < servers.length) {
                    return { value: servers[index++], done: false };
                } else {
                    return { done: true } as IteratorResult<CaptureServer>;
                }
            },
        };
    }

    /**
     * Implement the map function to apply a callback to all servers and return the results.
     * @param callback The function to apply to each server.
     * @returns An array of results from the callback function.
     */
    map<T>(callback: (server: CaptureServer, index: number) => T): Array<T> {
        return this.servers.map(callback);
    }
    /**
     * Execute callback on all servers and return a Promise that resolves when all callbacks have resolved.
     * If a callback rejects, the returned promise does not reject and instead logs a warning and continues.
     * @param callback The async function to run per server.
     * @param servers Optional subset of servers to operate on.
     * @returns A promise resolving to results (or nulls for failures).
     */
    allPromise<T = void>(callback: (server: CaptureServer) => Promise<T>, servers: CaptureServer[] = this.servers): Promise<(T | null)[]> {
        return Promise.all(servers.map(server => {
            return callback(server).catch((e) => {
                console.warn("Error in allPromise for server", server.url, ":", e);
                return null; // return null on error
            });
        }));
    }

    /**
     * Set a low timeout for all inactive servers (not connected).
     * Otherwise, we always send messages to these servers and wait for them to time out.
     * //TODO when implementing automatic reconnect, move this to reconnect logic
     */
    setLowTimeoutForInactiveServers(): void {
        const inactiveServers = this.servers.filter(s => s.socket.getSocket().readyState !== WebSocket.OPEN);
        inactiveServers.forEach(s => {
            s.socket.setDefaultSendOptions({ timeoutMs: 5 });
        });
    }

    /**
     * Prepare all servers for recording with given recording name and fps.
     * @param recordingName Name to set for recordings.
     * @param fps Frames per second to configure.
     * @returns A promise that resolves when preparation completes.
     */
    async prepareRecording(recordingName: string, fps: number = 30): Promise<void> {
        this.setLowTimeoutForInactiveServers();
        await this.allPromise(s => s.switchMode("record"));
        await triggerBox.setStateIfAvailable("off")
        await triggerBox.setStateIfAvailable(`set_fps_${fps}`);
        await this.allPromise(s => s.setFPS(fps));
        await this.allPromise(s => s.setRecordingName(recordingName));
    }

    /**
     * Prepare all servers and already put them in recording state so they only have to wait for the trigger.
     * @param recordingName Name to set for recordings.
     * @returns A promise that resolves when preparation completes.
     */
    async prepareRecordingSingle(recordingName: string): Promise<void> {
        await this.prepareRecording(recordingName, 1);
        await this.allPromise(s => s.startRecording());
    }

    /**
     * Trigger a single capture and stop recording on all servers.
     * @returns A promise that resolves when triggering completes.
     */
    async triggerSingle(): Promise<void> {
        // Trigger single image capture
        await triggerBox.setStateIfAvailable("single");

        // Stop recording
        await this.allPromise(s => s.stopRecording());
        await triggerBox.setStateIfAvailable("off");
    }

    /**
     * Prepare and record a single capture across all servers.
     * @param recordingName Name to set for recordings.
     * @returns A promise that resolves when the capture finishes.
     */
    async recordSingle(recordingName: string = "test-from-webapp"): Promise<void> {
        //TODO figure out why this always leads to buffer timout on server
        /**
         * folder with server: /home/administrator/trigger
         * screen -rx
         */
        await this.prepareRecordingSingle(recordingName);
        await this.triggerSingle();
    }
}
