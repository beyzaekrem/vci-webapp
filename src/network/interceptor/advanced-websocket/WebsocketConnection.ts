/**
 * Base WebSocket connection wrapper with reconnection and message processing hooks.
 * @packageDocumentation
 */
/**
 * Represents a WebSocket connection.
 * Handles initialization, reconnection and message processing.
 * @template RawMessageType - The type of the raw message received from the WebSocket.
 * @template ParsedMessageType - The type of the parsed message after processing.
 */
export class WebsocketConnection<
  RawMessageType = any,
  ParsedMessageType = RawMessageType,
> {
  #socket: WebSocket | undefined;
  #socketEvents: EventTarget;

  /**
   * Gets the native WebSocket instance.
   * @returns The WebSocket instance.
   */
  getSocket(): WebSocket {
    if(this.#socket === undefined) {
      throw new Error("Socket is not initialized! Call this method from somewhere you know the socket is initialized.");
    }
    return this.#socket;
  }

  /**
   * Gets the event target for socket events.
   * Can be used to listen for events like "newMessageData" or "changeReadyState".
   * @returns The event target.
   */
  getSocketEvents(): EventTarget {
    return this.#socketEvents;
  }



  /**
   * Creates a new WebsocketConnection.
   * @param url The WebSocket URL.
   * @param digestData Function to process raw message data. Can be used to parse or transform the data to a more usable format than Blob or string.
   * @param onNewMessage Function called when a new message is received. Called after digestData.
   * @param onConnected Function called when the WebSocket connection is established.
   */
  constructor(
    url: string,
    digestData: (data: RawMessageType) => Promise<ParsedMessageType>,
    onNewMessage = (message: ParsedMessageType) => { },
    onConnected = (ws: WebSocket) => { },
  ) {
    this.#socketEvents = new EventTarget();

    initWebSocket<RawMessageType, ParsedMessageType>(
      //url
      url,

      //socketEvents
      this.#socketEvents,

      //onReconnect
      (new_socket) => {
        this.#socket = new_socket;
      },

      //digestData
      digestData,

      //onNewMessage
      (message) => {
        onNewMessage(message);
      },

      onConnected,
    );
  }

}

/**
 * Initializes a WebSocket connection with reconnect and message-digest hooks.
 * @param url The WebSocket URL to connect to.
 * @param socketEvents EventTarget used to dispatch "newMessageData" and "changeReadyState" events.
 * @param onReconnect Callback invoked with the new socket instance.
 * @param digestDataBeforeOnNewMessage Function to parse raw data before emitting events.
 * @param onNewMessage Callback invoked with parsed message data.
 * @param onConnected Callback invoked when the socket is opened.
 * @returns The initialized WebSocket instance.
 */
function initWebSocket<RawMessageType, ParsedMessageType>(
  url: string,
  socketEvents: EventTarget,
  onReconnect = (retval: WebSocket) => { },
  digestDataBeforeOnNewMessage: (
    data: RawMessageType,
  ) => Promise<ParsedMessageType>,
  onNewMessage = (message: ParsedMessageType) => { },
  onConnected = (ws: WebSocket) => { },
) {
  var socket: WebSocket = new WebSocket(url); //TODO use isValidAddress before this step and throw error if invalid

  socket.addEventListener("message", (event) => {
    const lastMessage = event;

    var data = lastMessage.data;

    //digest data before calling onNewMessage
    try {
      digestDataBeforeOnNewMessage(data).then((digestedData) => {
        data = digestedData;
        const e = new CustomEvent("newMessageData", { detail: data });
        onNewMessage(data);
        socketEvents.dispatchEvent(e);
      });
    } catch(e) {
      console.warn(
        "Encountered an issue while digesting data '" + lastMessage?.data + "'",
      );
      console.warn(e);
    }
  });
  socket.onclose = (e) => {
    socketEvents.dispatchEvent(
      new CustomEvent("changeReadyState", { detail: socket.readyState }),
    );
    console.log(
      "Socket is closed. Reconnect will be attempted in 1 second.",
      e.reason,
    );
    setTimeout(() => {
      initWebSocket(
        url,
        socketEvents,
        onReconnect,
        digestDataBeforeOnNewMessage,
        onNewMessage,
        onConnected
      );
    }, 1000);
  };

  socket.onopen = () => {
    socketEvents.dispatchEvent(
      new CustomEvent("changeReadyState", { detail: socket.readyState }),
    );
    onConnected(socket);
  };

  //close connection when unloading page, not done automatically by browser
  window.addEventListener("beforeunload", function () {
    if(socket.readyState == WebSocket.OPEN) socket.close();
  });

  onReconnect(socket);

  return socket;
}

