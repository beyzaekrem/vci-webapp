/**
 * This module provides a factory function to create a singleton instance of a class that depends on a config stored in local storage.
 * The singleton instance is initialized with the stored config or defaults if not present.
 * It also provides a hook to access and update the stored config.
 * Used for both capture servers and control server to manage their addresses and ports in a consistent way.
 * @packageDocumentation
 */
import { useLocallyStored } from "./useLocallyStored";

/**
 * Configuration for the stored singleton, including default config value(s) and the name used in local storage.
 */
export type LocalStorageSettings<ConfigType> = {
    defaultConfig: ConfigType;
    nameInStorage: string;
};

/**
 * Reads the config value(s) from local storage or initializes them with defaults if not present.
 * @param param0 The local storage settings including the name and default config value(s).
 * @returns The stored config value(s).
 * @throws If it fails to set the defaults in local storage.
 */
function readOrInitConfig<ConfigType>({ nameInStorage, defaultConfig }: LocalStorageSettings<ConfigType>): ConfigType {
    const saved = localStorage.getItem(nameInStorage);
    if(saved !== null) {
        try {
            return JSON.parse(saved) as ConfigType;
        } catch {
            return saved as ConfigType;
        }
    }

    localStorage.setItem(nameInStorage, JSON.stringify(defaultConfig));
    const savedAgain = localStorage.getItem(nameInStorage);
    if(savedAgain === null) throw new Error(`Could not set defaults for ${nameInStorage}`);

    try {
        return JSON.parse(savedAgain) as ConfigType;
    } catch {
        return savedAgain as ConfigType;
    }
}

type StoredSingleton<TInstance, ConfigType> = {
    /**
     * Initializes the singleton instance with the provided configuration. Reads the config value(s) from local storage or initializes them with defaults if not present.
     * @param c The local storage settings including the name and default config value(s).
     */
    init: (config: LocalStorageSettings<ConfigType>) => void;
    /**
     * Gets the singleton instance. Throws an error if the instance has not been initialized yet.
     * @returns The singleton instance.
     */
    get: () => TInstance;
    /**
     * React hook to access and update the stored config value(s). Uses the local storage settings provided during initialization.
     * @returns A tuple of [configValue, setConfigValue].
     */
    useLocallyStoredConfig: () => [ConfigType, (value: ConfigType) => void];
    /**
     * Reloads the singleton instance with the current config value(s) from local storage. Useful to apply changes after updating the config.
     */
    reload: () => void;
};

/**
 * Factory function for creating a singleton instance of a class that depends on a config stored in local storage.
 * Call this function to create the singleton and then use the returned init function to initialize it with the appropriate config.
 * The instance is initialized with the stored config value(s) or defaults if not present.
 * Provides a hook to access and update the stored config value(s).
 * @param build A function that takes the config value(s) and config to create the instance.
 * @returns An object with init, get, and useLocallyStoredConfig functions.
 */
export function createStoredSingleton<TInstance, ConfigType = string[]>(
    build: (config: ConfigType, localStorageSettings: LocalStorageSettings<ConfigType>) => TInstance
): StoredSingleton<TInstance, ConfigType> {
    let instance: TInstance | null = null;
    let localStorageSettings: LocalStorageSettings<ConfigType> | null = null;

    function init(c: LocalStorageSettings<ConfigType>): void {
        localStorageSettings = c;
        reload();
    }

    function get(): TInstance {
        if(!instance) throw new Error("Not initialized!");
        return instance;
    }

    function reload(): void {
        if(!localStorageSettings) throw new Error("Not initialized!");
        const config = readOrInitConfig(localStorageSettings);
        instance = build(config, localStorageSettings);
    }

    function getFromStorageProps(): LocalStorageSettings<ConfigType> {
        if(!localStorageSettings) throw new Error("Not initialized!");
        return localStorageSettings;
    }

    function useLocallyStoredConfig(): [ConfigType, (value: ConfigType) => void] {
        const c = getFromStorageProps();
        return useLocallyStored<ConfigType>(c.nameInStorage, c.defaultConfig);
    }

    return { init, get, useLocallyStoredConfig, reload };
}
