/**
 * Represents a control server. Uses an InterceptorConnection to communicate with the server.
 * @packageDocumentation
 */
import {
  InterceptorConnection,
  Message
} from "../interceptor";

/**
 * Represents a control server. Uses an InterceptorConnection to communicate with the server.
 */
export class ControlServer {
  socket: InterceptorConnection;

  /**
   * Creates a ControlServer client for the given WebSocket URL.
   * @param url The control server WebSocket URL.
   */
  constructor(public url: string) {
    this.socket = new InterceptorConnection(url);
  }

  /**
   * Request the current control server status.
   * @returns A promise resolving to the status payload.
   */
  getStatus(): Promise<Message["PAYLOAD"][number]> {
    return this.socket.send({
      TYPE: 3, // StandardMessage
      PATH: "STATUS",
      PAYLOAD: [],
    }).then((response) => {
      return response.PAYLOAD[0];
    });
  }

  /**
   * Request the control server to connect.
   * @returns A promise resolving to the server response.
   */
  connect(): Promise<Message> {
    return this.socket.send({
      TYPE: 3, // StandardMessage
      PATH: "CONNECT",
      PAYLOAD: [],
    });
  }

  /**
   * Request camera positions from the control server.
   * @returns A promise resolving to the positions payload.
   */
  getCameraPositions(): Promise<Message["PAYLOAD"][number]> {
    return this.socket.send({
      TYPE: 3, // StandardMessage
      PATH: "GET_POSITION_OF_CAMERAS",
      PAYLOAD: [],
    }).then((response) => {
      return response.PAYLOAD[0];
    });
  }

  //TODO integrate other functionality from control server and build a UI for it
}
