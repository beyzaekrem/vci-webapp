/**
 * Contains all functionality used for communicating with the capture server.
 * 
 * The connections can be managed as singletons (see CaptureServersSingleton.ts and ControlServerSingleton.ts)
 * and are initialized in main.tsx. They can then be accessed throughout the app via the get functions of the respective singletons.
 * @packageDocumentation
 */

export * from "./Hooks";
export * from "./CaptureServersSingleton";
export * from "./CameraSystemData";