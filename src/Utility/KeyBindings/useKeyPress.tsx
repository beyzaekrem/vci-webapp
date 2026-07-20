/**
 * Hook and types for registering a keydown shortcut and exposing it in the key binding UI.
 * Manages listener setup and context registration for a single key press action.
 * @packageDocumentation
 */

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useKeyBindingContext } from "./context";
import { KeyBindingInfo, KeyPressArgs, normalizeCategory } from "./types";
import { isGlobalShortcutAllowed } from "./utils";


/** Args for registering a key press with optional UI metadata. */
export type KeyPressRegistrationArgs = KeyPressArgs & {
  eventDescription?: string;
};

/** Register a keydown shortcut and add it to the key binding menu. */
export function useKeyPress(pArgs: KeyPressRegistrationArgs): void {
  const { addKeyBinding, removeKeyBinding } = useKeyBindingContext();

  const onKeyEventRef = useRef(pArgs.onKeyEvent);
  useEffect((): void => {
    onKeyEventRef.current = pArgs.onKeyEvent;
  }, [pArgs.onKeyEvent]);

  const depsKey = useMemo(
    (): string => JSON.stringify(pArgs.dependencies ?? []),
    [pArgs.dependencies],
  );

  const action = useCallback((): void => {
    onKeyEventRef.current();
  }, []);

  const bindingInfo = useMemo<KeyBindingInfo>(
    (): KeyBindingInfo => ({
      description: pArgs.description,
      category: normalizeCategory(pArgs.category),
      icon: pArgs.icon,
      eventDescription: pArgs.eventDescription ?? pArgs.key,
      action,
    }),
    [
      pArgs.description,
      pArgs.category,
      pArgs.icon,
      pArgs.key,
      pArgs.eventDescription,
      action,
      depsKey,
    ],
  );

  useEffect((): void | (() => void) => {
    addKeyBinding(bindingInfo);
    return () => {
      removeKeyBinding(bindingInfo);
    };
  }, [bindingInfo, addKeyBinding, removeKeyBinding, depsKey]);

  /** Handle the window keydown event for this binding. */
  function keyEv(e: KeyboardEvent): void {
    if((isGlobalShortcutAllowed() && e.key == pArgs.key) || e.code == pArgs.key) {
      onKeyEventRef.current();
    }
  }

  useEffect((): void | (() => void) => {
    const event = "keydown";
    window.addEventListener(event, keyEv);
    return () => {
      window.removeEventListener(event, keyEv);
    };
  }, [pArgs.key, depsKey]);
}
