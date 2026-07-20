/**
 * Contains all functionality used for communicating with the control server.
 * 
 * The instance of the connection is created via the init function from ControlServerSingleton and is called in main.tsx.
 * The instance can then be accessed via the get function from ControlServerSingleton.
 * @packageDocumentation
 */

export * from "./ControlServerSingleton";
export * from "./Hooks";