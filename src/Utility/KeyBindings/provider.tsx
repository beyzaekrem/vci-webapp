/**
 * Provider component for key binding state and registration.
 * Wraps children with context and mounts the global help menu.
 * @packageDocumentation
 */

import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { KeyBindingContext } from "./context";
import type { KeyBindingContextValue } from "./context";
import { KeyBindingInfo } from "./types";
import { KeyBindingMenu } from "./menu";

/** Context provider that tracks key bindings and renders the help menu. */
export function WithKeyBindingContext({ children }: { children: ReactNode }): JSX.Element {
  const [keyBindings, setKeyBindings] = useState(new Array<KeyBindingInfo>());

  const addKeyBinding = useCallback((binding: KeyBindingInfo): void => {
    setKeyBindings((prev: KeyBindingInfo[]): KeyBindingInfo[] => {
      if(
        prev.some(
          (k: KeyBindingInfo): boolean =>
            k.eventDescription == binding.eventDescription &&
            k.description == binding.description,
        )
      ) {
        return prev;
      }
      return [...prev, binding];
    });
  }, []);

  const removeKeyBinding = useCallback((binding: KeyBindingInfo): void => {
    setKeyBindings((prev: KeyBindingInfo[]): KeyBindingInfo[] =>
      prev.filter((k: KeyBindingInfo): boolean => k != binding),
    );
  }, []);

  const contextValue = useMemo<KeyBindingContextValue>(
    (): KeyBindingContextValue => ({ keyBindings, addKeyBinding, removeKeyBinding }),
    [keyBindings, addKeyBinding, removeKeyBinding],
  );

  return (
    <KeyBindingContext.Provider value={contextValue}>
      <KeyBindingMenu />
      {children}
    </KeyBindingContext.Provider>
  );
}
