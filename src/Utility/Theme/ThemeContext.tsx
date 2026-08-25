/**
 * @packageDocumentation
 * Global theme context providing dark/light mode toggle with localStorage persistence.
 * Applies the active theme via `data-theme` attribute on the <html> element.
 */
import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
} from "react";

export type ThemeMode = "dark" | "light";

interface ThemeContextType {
    theme: ThemeMode;
    toggleTheme: () => void;
    setTheme: (mode: ThemeMode) => void;
}

const STORAGE_KEY = "vci-theme";
const DEFAULT_THEME: ThemeMode = "dark";

const ThemeContext = createContext<ThemeContextType>({
    theme: DEFAULT_THEME,
    toggleTheme: () => {},
    setTheme: () => {},
});

export function useTheme(): ThemeContextType {
    return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<ThemeMode>(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored === "dark" || stored === "light") return stored;
        } catch {
            // ignore
        }
        return DEFAULT_THEME;
    });

    // Apply data-theme to <html> element whenever theme changes
    useEffect(() => {
        document.documentElement.setAttribute("data-theme", theme);
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch {
            // ignore
        }
    }, [theme]);

    const setTheme = useCallback((mode: ThemeMode) => {
        setThemeState(mode);
    }, []);

    const toggleTheme = useCallback(() => {
        setThemeState((prev) => (prev === "dark" ? "light" : "dark"));
    }, []);

    return (
        <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}
