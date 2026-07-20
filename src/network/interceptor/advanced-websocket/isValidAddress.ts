/**
 * Validates if a string is a valid IP address or hostname for use in WebSocket connections.
 * @packageDocumentation
 */

/**
 * Checks if the given string is a valid IP address or hostname.
 * No protocols, ports, paths, query parameters or authentication information are allowed.
 * @param value The string to validate as an address.
 * @returns True if the string is a valid IP address or hostname, false otherwise.
 */
export const isValidAddress = (value: string): boolean => {
    if(value.length === 0) return false;
    if(value.trim() !== value) return false;
    if(value.includes("://")) return false;
    if(value.includes("/") || value.includes("@")) return false;
    if(value.includes(":")) return false;
    if(/\s/.test(value)) return false;

    if(isValidIPv4(value)) return true;
    return isValidHostname(value);
};

/**
 * Checks if the given string is a valid IPv4 address.
 * @param value The string to validate.
 * @returns True if the string is a valid IPv4 address.
 */
const isValidIPv4 = (value: string): boolean => {
    const parts = value.split(".");
    if(parts.length !== 4) return false;

    const octetPattern = /^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;
    return parts.every((part) => octetPattern.test(part));
};

/**
 * Checks if the given string is a valid hostname (RFC-ish).
 * @param value The string to validate.
 * @returns True if the string is a valid hostname.
 */
const isValidHostname = (value: string): boolean => {
    if(value.length > 253) return false;
    if(value.startsWith(".") || value.endsWith(".")) return false;

    const labels = value.split(".");
    if(labels.length === 0) return false;

    const labelPattern = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i;
    return labels.every((label) => labelPattern.test(label));
};
