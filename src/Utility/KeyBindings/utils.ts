/**
 * Utility helpers for grouping and describing key binding data.
 * Includes category sorting and key display helpers.
 * @packageDocumentation
 */

import { KeyBindingInfo } from "./types";

/** Mapping function used for grouping values. */
export type MapFunc<T = any> = (val: T, index?: number, arr?: T[]) => T;

/** Group array elements by a property name or mapping function. */
export function groupBy<T = any>(
  arr: T[],
  fn: MapFunc<T> | string,
): Record<string, T[]> {
  return arr
    .map(typeof fn === "string" ? (val: T): T => (val as any)[fn] : fn)
    .reduce(
      (acc: Record<string, T[]>, val: T, i: number): Record<string, T[]> => {
        acc[String(val)] = (acc[String(val)] || []).concat(arr[i]);
        return acc;
      },
      {} as Record<string, T[]>,
    );
}

/** Return sorted categories, keeping "Other" last. */
export function getCategories(keyBindings: KeyBindingInfo[]): string[] {
  let categories = [...new Set(keyBindings.map((o: KeyBindingInfo): string => o.category))].sort();
  if(categories.indexOf("Other") >= 0) {
    categories = categories.filter((o: string): boolean => o != "Other");
    categories.push("Other");
  }
  return categories;
}

/** Human-friendly description for a key identifier. */
export function getKeyDescription(key?: string): string {
  if(key === undefined) return "undefined";
  //if the key is F1-F12, return it as is
  if(key.startsWith("F") && key.length > 1 && !isNaN(parseInt(key.substring(1)))) {
    return key;
  }
  return key === key.toUpperCase() ? `Shift + ${key.toLocaleLowerCase()}` : key;
}


/** Return true when no text input/textarea has focus. */
export function isGlobalShortcutAllowed(): boolean {
  if(!document.activeElement) return true;
  return ["INPUT", "TEXTAREA"].indexOf(document.activeElement.tagName) < 0;
}
