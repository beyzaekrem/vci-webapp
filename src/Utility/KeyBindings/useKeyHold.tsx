/**
 * Hook for registering key hold bindings with separate keydown and keyup handlers.
 * Includes menu registration for a toggle-style hold action.
 * @packageDocumentation
 */

/**
 * Hook for registering a key hold binding (separate down/up handlers).
 * Legacy/unused, check if we still need that
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useKeyBindingContext } from "./context";
import { KeyBindingArgs, KeyBindingInfo, KeyCallback, KeyPressArgs, normalizeCategory } from "./types";
import { isGlobalShortcutAllowed } from "./utils";


/** Args for a key hold binding (separate down/up handlers). */
export interface KeyHoldArgs extends KeyBindingArgs {
    onKeyDown: KeyCallback;
    onKeyUp: KeyCallback;
}

/** Register a shortcut that fires on keydown and keyup, plus a menu action. */
export function useKeyHoldShortcut(args: KeyHoldArgs): void {
    const depsKey = useMemo(
        (): string => JSON.stringify(args.dependencies ?? []),
        [args.dependencies],
    );

    const keydownArgs = useMemo<KeyPressArgs>(
        (): KeyPressArgs => ({
            key: args.key,
            description: args.description,
            category: args.category,
            icon: args.icon,
            dependencies: args.dependencies,
            onKeyEvent: args.onKeyDown,
        }),
        [
            args.key,
            args.description,
            args.category,
            args.icon,
            args.onKeyDown,
            args.dependencies,
            depsKey,
        ],
    );

    const keyupArgs = useMemo<KeyPressArgs>(
        (): KeyPressArgs => ({
            key: args.key,
            description: args.description,
            category: args.category,
            icon: args.icon,
            dependencies: args.dependencies,
            onKeyEvent: args.onKeyUp,
        }),
        [
            args.key,
            args.description,
            args.category,
            args.icon,
            args.onKeyUp,
            args.dependencies,
            depsKey,
        ],
    );

    useWindowKeyDownListener(keydownArgs);
    useWindowKeyUpListener(keyupArgs);

    //Set Hold by clicking on menu, or release by clicking again
    const [, setFakeHold] = useState(false);
    useEffect((): void | (() => void) => {
        const resetFakeHold = (): void => setFakeHold(false);
        window.addEventListener("keydown", resetFakeHold);
        window.addEventListener("keyup", resetFakeHold);
        return () => {
            window.removeEventListener("keydown", resetFakeHold);
            window.removeEventListener("keyup", resetFakeHold);
        };
    }, [depsKey]);

    const toggleFakeHold = useCallback((): void => {
        setFakeHold((hold: boolean): boolean => {
            if(hold) {
                args.onKeyUp();
            } else {
                args.onKeyDown();
            }
            return !hold;
        });
    }, [args.onKeyDown, args.onKeyUp]);

    const holdAction = useMemo<KeyBindingInfo>(
        (): KeyBindingInfo => ({
            description: args.description,
            category: normalizeCategory(args.category),
            icon: args.icon,
            eventDescription: "Hold " + args.key,
            action: toggleFakeHold,
        }),
        [
            args.description,
            args.category,
            args.icon,
            args.key,
            toggleFakeHold,
            depsKey,
        ],
    );

    useRegisterKeyBinding(holdAction);
}

/** Register a window-level keydown listener. */
function useWindowKeyDownListener(args: KeyPressArgs): void {
    useWindowKeyEventListener(args, "keydown");
}

/** Register a window-level keyup listener. */
function useWindowKeyUpListener(args: KeyPressArgs): void {
    useWindowKeyEventListener(args, "keyup");
}

/** Attach a window listener for the given key event. */
function useWindowKeyEventListener(
    keyB: KeyPressArgs,
    event: string,
): void {
    function keyEv(e: any): void {
        if((isGlobalShortcutAllowed() && e.key == keyB.key) || e.code == keyB.key) {
            keyB.onKeyEvent();
        }
    }
    useEffect((): void | (() => void) => {
        window.addEventListener(event, keyEv);
        return () => {
            window.removeEventListener(event, keyEv);
        };
    }, [keyB.dependencies, keyB.onKeyEvent, keyB.key]);
}


/** Register an action with the key binding context for UI menus. */
function useRegisterKeyBinding(keyBinding: KeyBindingInfo): void {
    const { addKeyBinding, removeKeyBinding } = useKeyBindingContext();
    useEffect((): void | (() => void) => {
        addKeyBinding(keyBinding);
        return () => {
            removeKeyBinding(keyBinding);
        };
    }, [keyBinding, addKeyBinding, removeKeyBinding]);
}
