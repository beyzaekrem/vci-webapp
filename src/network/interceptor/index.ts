/**
 * This module contains functionality for communicating with a server that uses interceptor.
 * It uses the advanced-websocket module for the underlying WebSocket connection.
 * capture-server and control-server extend InterceptorConnection to provide app-specific functionality.
 * 
 * @remarks
 * - `InterceptorConnection`: Represents a WebSocket connection using the message format for interceptor.
 * - `Message`: Defines message structures and utilities for network communication.
 * 
 * @packageDocumentation
 */
export * from "./InterceptorConnection"
export type { Message } from "./Message"
export { MessageType } from "./Message"
export {
  useConnectionStatus,
  ReadyState,
  isValidAddress,
  readyStateToString,
  ServerStatusInfo,
} from "./advanced-websocket"
