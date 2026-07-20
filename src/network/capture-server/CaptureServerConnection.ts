/**
 * This module defines the CaptureServerConnection class, which extends the InterceptorConnection class
 * to handle specific messages and events related to the capture server,
 * such as livestreaming and camera information retrieval.
 * @packageDocumentation
 */

import { CameraSystemData } from "./CameraSystemData";
import { MessageType, Message } from "../interceptor";
import { InterceptorConnection } from "../interceptor";


/**
 * Extension of the InterceptorConnection class for the capture server.
 * Adds functionality for handling the capture server's specific messages and events, e.g. livestreaming.
 */
export class CaptureServerConnection extends InterceptorConnection {
    #currentCamToolState: CameraSystemData | undefined = undefined;

    /**
     * Creates a CaptureServerConnection and registers default listeners.
     * @param url The capture server WebSocket URL.
     */
    constructor(url: string) {
        super(
            url,
            // onReconnect
            () => {
                this.send({
                    PATH: "SWITCH_MODE",
                    TYPE: 3, // StandardMessage
                    PAYLOAD: [
                        {
                            mode: "livestream",
                        },
                    ],
                }).then((msg) => {
                    console.log("Switched to livestream mode: ", msg);

                    // Request all information from the cameras at start
                    this.requestAllInfo();
                })

            }
        );

        // print all messages except for STREAM_CONTENT
        this.addListener((message) => {
            if(message.PATH !== "STREAM_CONTENT" && message.PATH !== "POLL_LIVESTREAM_IMAGE") {
                console.log(message);
            }
        });

        // handle some messages specifically, all others can be handled by adding a listener (see InterceptorConnection)
        this.addListener((message) => {
            if(message.TYPE === MessageType.AcknowledgeResponse) {
                if(message.PATH === "GET_ALL_INFO") {
                    this.#currentCamToolState = message
                        .PAYLOAD[0] as CameraSystemData;
                }
            }
        });
    }

    /**
     * Requests all camera information from the capture server.
     * @returns A promise that resolves with the response message containing all camera information.
     */
    requestAllInfo(): Promise<Message> {
        const message = {
            TYPE: 3, // StandardMessage
            PATH: "GET_ALL_INFO",
            PAYLOAD: [],
        };

        return this.send(message);
    }

    /**
     * Gets the current camera tool state containing all camera information.
     * @returns The latest camera system data, if available.
     */
    getCurrentCamToolState(): CameraSystemData | undefined {
        return this.#currentCamToolState;
    }

    /**
     * Adds a listener for stream messages with the specified stream ID.
     * @param stream_id The stream ID to listen for.
     * @param listener The listener function to call when a new message with the specified stream ID is received.
     * The listener function receives the message payload and the capture time as arguments.
     * @returns The listener function that was added (can be used to remove the listener later).
     */
    addStreamListener(stream_id: string, listener: (msg: Uint8Array, capture_time: number) => void): (msg: Message) => void {
        const onNewMessage = (msg: Message) => {
            if(msg.PATH === "STREAM_CONTENT" &&
                msg.PAYLOAD[0].stream_id === stream_id) {
                let capture_time = msg.PAYLOAD[0].capture_time; // from pythons time.time()
                const threshold = 200; //in ms
                if(Date.now() - capture_time * 1000 > threshold) {
                    console.warn("Received an image that was captured more than " + threshold + " ms ago. discarding it");
                }
                else {
                    listener(msg.PAYLOAD[1] as Uint8Array, capture_time);
                }
            }
        };
        this.addListener(onNewMessage);
        return onNewMessage;
    }

    /**
     * Removes a listener for stream messages.
     * @param listener The listener function to remove.
     */
    removeStreamListener(listener: (msg: Message) => void): void {
        this.removeListener(listener);
    }
}
