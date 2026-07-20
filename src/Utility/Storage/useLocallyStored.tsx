import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

// 1) Define the shape of our context
/**
 * Local storage context shape for in-memory cache and writes.
 */
interface LocalStorageContextProps {
  /** Current in-memory snapshot keyed by storage key. */
  items: Record<string, any>;
  /** Updates the in-memory cache and writes through to localStorage. */
  setItem: (key: string, value: any) => void;
}

// 2) Create the context
const LocalStorageContext = createContext<LocalStorageContextProps>({
  items: {},
  setItem: () => { },
});

// 3) Create the provider
/**
 * Provides localStorage-backed values to descendants.
 * @param children React children to wrap with the provider.
 * @returns Provider element that supplies local storage context.
 */
export function LocalStorageProvider({ children }: { children: ReactNode }) {
  // We keep a map of key -> value in state.
  const [items, setItems] = useState<Record<string, any>>({});

  const serializeForStorage = useCallback((value: any) => {
    if(typeof value === "string") {
      return value;
    }
    return JSON.stringify(value);
  }, []);

  // This function updates the in-memory map *and* writes to localStorage.
  const setItem = useCallback((key: string, value: any) => {
    setItems((prev) => ({ ...prev, [key]: value }));
    localStorage.setItem(key, serializeForStorage(value));
  }, [serializeForStorage]);

  // Memoize our context value so we don't cause unnecessary re-renders.
  const contextValue = useMemo(() => {
    return { items, setItem };
  }, [items, setItem]);

  return (
    <LocalStorageContext.Provider value={contextValue}>
      {children}
    </LocalStorageContext.Provider>
  );
}

// The type parameter <T> is optional but helps with typing.
/**
 * Reads a value from localStorage (with an in-memory cache) and provides a setter.
 * @param key Storage key to read/write.
 * @param defaultValue Fallback value when nothing is stored yet.
 * @returns Tuple of current value and a setter that persists updates.
 */
export function useLocallyStored<T>(
  key: string,
  defaultValue: T,
): [T, (value: T) => void] {
  const { items, setItem } = useContext(LocalStorageContext);

  // The current value in context for this key (might be undefined if first time)
  const contextValue = items[key];

  // If the key has never been set in the context, read from localStorage or use default:
  useEffect(() => {
    if(contextValue === undefined) {
      const storedValue = localStorage.getItem(key);
      let initialValue = defaultValue;

      if(storedValue !== null) {
        if(typeof defaultValue === "string") {
          try {
            const parsed = JSON.parse(storedValue);
            initialValue = (typeof parsed === "string" ? parsed : storedValue) as T;
          } catch {
            initialValue = storedValue as T;
          }
        } else {
          try {
            initialValue = JSON.parse(storedValue);
          } catch {
            initialValue = defaultValue;
          }
        }
      }

      setItem(key, initialValue);
    }
  }, [contextValue, key, defaultValue, setItem]);

  // The setter simply updates the context (which also writes to localStorage).
  const setStoredValue = (newValue: T) => {
    setItem(key, newValue);
  };

  // If `contextValue` is still undefined (during first render), temporarily return `defaultValue`.
  return [contextValue ?? defaultValue, setStoredValue];
}
