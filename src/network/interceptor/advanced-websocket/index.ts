/**
 * A module that provides some additional functionality for general webSocket connections.
 * 
 * @packageDocumentation
 */

export * as Connection from "./WebsocketConnection";
export { isValidAddress } from "./isValidAddress";
export { useConnectionStatus, ReadyState, readyStateToString } from "./ConnectionStatus";
export { ServerStatusInfo } from "./ServerStatusInfo";
