/**
 * WebSocket connection for sending and receiving interceptor messages with BSON encoding.
 * Provides message listeners and request/response helpers with retry and timeout support.
 * @packageDocumentation
 */
import { Message, decodeWebsocketMessage, encodeWebsocketMessage } from "./Message";
import { WebsocketConnection } from "./advanced-websocket/WebsocketConnection";

/**
 * Options controlling retries and timeouts for request/response sends.
 */
type SendOptions = {
    /** Number of retries if no response is received */
    retries: number;

    /** Delay between retries in milliseconds */
    delayMs: number;

    /** Timeout for waiting for a response in milliseconds */
    timeoutMs: number;
};

/**
 * Websocket Connection you can use to send and receive messages as defined in interceptor.
 * Handles encoding and decoding of messages in BSON format.
 * Provides a way to add listeners for new messages and to send messages with a callback for the response.
 */

export class InterceptorConnection extends WebsocketConnection<
    any, Message
> {

    #onNewMessage: Set<(msg: Message) => void> = new Set();
    #messageCount = 0;
    #defaultSendOptions: SendOptions = {
        retries: 5,
        delayMs: 500,
        timeoutMs: 3000,
    };

    /**
     * Creates a new InterceptorConnection.
     * @param url The URL of the WebSocket server.
     * @param onReconnect A callback function that is called when the connection is re-established, e.g. for switching to a specific mode.
     * Re-adding handlers on reconnect is not necessary, as they are kept constant over reconnects.
     */
    constructor(url: string, onReconnect: (ws: WebSocket) => void = () => { }) {
        super(
            url,
            // digestData: decode from Blob to Message
            (data) => {
                const _data = data as Blob;
                return _data.arrayBuffer().then((buffer) => {
                    const startTime = performance.now();
                    const msg = decodeWebsocketMessage(buffer);
                    const endTime = performance.now();
                    //console.log(`Decoding websocket message took ${endTime - startTime} milliseconds`);
                    //throw new Error("we have to throw an error here so the client does not crash because current cam tool state is not set");
                    return msg;
                });
            },
            (message) => {
                this.#onNewMessage.forEach((listener) => listener(message));
            },
            onReconnect
        );
    }

    /**
     * Sends a message and waits for a response with the same ID.
     * Retries sending the message if no response is received within the timeout.
     * @param message The message to send (without the ID field).
     * @param options Optional send options (retries, delayMs, timeoutMs). Can override default options set by setDefaultSendOptions.
     * @returns A promise that resolves with the response message.
     */
    send(message: MessageToSend, options?: Partial<SendOptions>): Promise<Message> {
        const { retries, delayMs, timeoutMs } = { ...this.#defaultSendOptions, ...options };

        // Freeze ID for all attempts, increment counter once
        const id = this.#messageCount++;
        const msg: Message = { ...message, ID: id };

        return new Promise<Message>((resolve, reject) => {
            let attempt = 0;
            let timeoutHandle: any | undefined;

            const cleanup = (onResp: (m: Message) => void) => {
                this.#onNewMessage.delete(onResp);
                if(timeoutHandle) clearTimeout(timeoutHandle);
            };

            const tryOnce = () => {
                attempt++;
                const socket = this.getSocket();

                if(socket.readyState !== WebSocket.OPEN) {
                    if(attempt <= retries + 1) {
                        setTimeout(tryOnce, delayMs);
                        return;
                    }
                    reject(new DOMException(
                        `WebSocket is not open. Current readyState: ${socket.readyState}`,
                        "InvalidStateError"
                    ));
                    return;
                }

                // Try to send
                try {
                    // Re-encode for each attempt so retries never reuse a transferred buffer.
                    const buffer = encodeWebsocketMessage(msg);
                    socket.send(buffer);
                } catch(e) {
                    // Browsers can throw different DOMExceptions here while a socket is still not usable.
                    if(e instanceof DOMException && attempt <= retries + 1) {
                        setTimeout(tryOnce, delayMs);
                        return;
                    }
                    reject(e);
                    return;
                }

                // Wait for matching response
                const onResp = (responseMsg: Message) => {
                    if(responseMsg.ID === id) {
                        cleanup(onResp);
                        resolve(responseMsg);
                    }
                };

                this.#onNewMessage.add(onResp);

                // Optional per-attempt timeout (helps when the send succeeds but no reply arrives)
                if(timeoutMs) {
                    timeoutHandle = setTimeout(() => {
                        cleanup(onResp);
                        if(attempt <= retries) {
                            setTimeout(tryOnce, delayMs);
                        } else {
                            reject(new Error(`No response after ${attempt} attempt(s)`));
                        }
                    }, timeoutMs);
                }
            };

            tryOnce();
        });
    }

    /**
     * Adds a listener for new messages. Do this after creating the InterceptorConnection, not on reconnects.
     * @param listener The listener function to add.
     */
    addListener(listener: (msg: Message) => void) {
        this.#onNewMessage.add(listener);
    }

    /**
     * Removes a listener for new messages.
     * @param listener The listener function to remove.
     */
    removeListener(listener: (msg: Message) => void) {
        this.#onNewMessage.delete(listener);
    }

    /**
     * Sets the default send options for all messages.
     * @param options The send options to set.
     */
    setDefaultSendOptions(options: Partial<SendOptions>) {
        this.#defaultSendOptions = { ...this.#defaultSendOptions, ...options };
    }
}

/**
 * Type for a message to be sent via the interceptor connection. does not include the ID field because it is set by the InterceptorConnection.
 */
type MessageToSend = Omit<Message, "ID">;
