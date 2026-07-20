/**
 * Hook utilities for WebSocket connection status and ready state helpers.
 * @packageDocumentation
 */
import { useEffect, useState } from "react";
import {
  WebsocketConnection
} from "./WebsocketConnection";

/**
 * This hook is used to get the connection status of a websocket connection.
 * @param webSocketConnection The WebSocket wrapper instance.
 * @returns The current WebSocket readyState value.
 */
export function useConnectionStatus(
  webSocketConnection: WebsocketConnection<any, any>,
): number {
  const ws = webSocketConnection;

  const [state, setState] = useState(ws.getSocket().readyState);
  useEffect(() => {
    setState(ws.getSocket().readyState);
    ws.getSocketEvents().addEventListener("changeReadyState", change);
    return () => {
      ws.getSocketEvents().removeEventListener("changeReadyState", change);
    };
  }, []);

  function change(e: any) {
    setState(e.detail);
  }
  return state;
}

/**
 * This enum is used to represent the different states of a websocket connection.
 * It is used in the useConnectionStatus hook to determine the current state of the connection.
 */
export enum ReadyState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3,
  UNINSTANTIATED = -1
}

/**
 * Converts a WebSocket readyState value into a human-readable string.
 * @param readyState The numeric readyState value.
 * @returns The corresponding string label.
 */
export function readyStateToString(readyState: number): string | undefined {
  return {
    [ReadyState.CONNECTING]: "Connecting",
    [ReadyState.OPEN]: "Open",
    [ReadyState.CLOSING]: "Closing",
    [ReadyState.CLOSED]: "Closed",
    [ReadyState.UNINSTANTIATED]: "Uninstantiated",
  }[readyState];
}
