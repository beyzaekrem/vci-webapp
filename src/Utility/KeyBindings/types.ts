/**
 * Type definitions for key binding metadata, callbacks, and args.
 * Normalizes categories and describes binding payloads used by the module.
 * @packageDocumentation
 */

/** Callback signature for key actions. */
export type KeyCallback = () => void;

/** Shared UI metadata for anything that can be shown as an action. */
export interface ActionMetadata {
  description: string;
  category?: string;
  icon?: any;
}

/** Base args for defining a key binding. */
export interface KeyBindingArgs extends ActionMetadata {
  key: string;
  dependencies?: any[];
}

/** Common fields for all key bindings with normalized category. */
export interface KeyBinding extends KeyBindingArgs {
  category: string;
}

/** Args for a single key event binding (keydown/keyup). */
export interface KeyPressArgs extends KeyBindingArgs {
  onKeyEvent: KeyCallback;
}


/** UI-facing info for an action to show in menus and buttons. */
export interface KeyBindingInfo extends ActionMetadata {
  eventDescription: string;
  action: KeyCallback;
  category: string;
}

/** Normalize a category value for display. */
export function normalizeCategory(category?: string): string {
  return category && category.trim().length > 0 ? category : "Other";
}
