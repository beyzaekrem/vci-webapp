/**
 * Key binding system for registering and handling keyboard shortcuts.
 * Provides a system where you can register actions to be run when a specific key is pressed.
 * Registered actions will be shown in the help menu or menus for specific categories.
 * The actions can then also be executed by clicking the buttons in the menus.
 * Functions for displaying a Button for a registered action
 * (or displaying menus for specific categories) are also provided and can be used anywhere.
 * @packageDocumentation
 */

export * from "./types";
export * from "./context";
export * from "./useKeyPress";
export * from "./menu";
export * from "./provider";
export * from "./utils";
