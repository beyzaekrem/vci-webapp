/**
 * React context and hooks for accessing registered key bindings.
 * Provides lookup helpers for UI actions.
 * @packageDocumentation
 */

import { createContext, useContext } from "react";
import { KeyBindingInfo } from "./types";

/** Shape of the key binding context value. */
export interface KeyBindingContextValue {
  keyBindings: KeyBindingInfo[];
  addKeyBinding: (binding: KeyBindingInfo) => void;
  removeKeyBinding: (binding: KeyBindingInfo) => void;
}

const defaultContextValue: KeyBindingContextValue = {
  keyBindings: [],
  addKeyBinding: (_binding: KeyBindingInfo): void => { },
  removeKeyBinding: (_binding: KeyBindingInfo): void => { },
};

export const KeyBindingContext = createContext<KeyBindingContextValue>(
  defaultContextValue,
);

/** Access the key binding context value. */
export function useKeyBindingContext(): KeyBindingContextValue {
  return useContext(KeyBindingContext);
}

/** Lookup a registered action by its event description. */
export function useAction(eventDescription: string): KeyBindingInfo | undefined {
  const x = useKeyBindingContext();
  const actions = x.keyBindings.filter(
    (kb: KeyBindingInfo): boolean => kb.eventDescription == eventDescription,
  );
  if(actions.length == 0) {
    console.warn("Action " + eventDescription + " not found!");
    return undefined;
  }
  return actions[0];
}
