/**
 * This module provides a utility function to download images as JPEG files in the browser.
 * @packageDocumentation
 */

/**
 * Downloads an images as a JPEG file.
 * @param img The image data as a Uint8Array.
 * @param filename The filename to save the image as.
 */
export function downloadImage(img: Uint8Array<ArrayBufferLike>, filename: string) {
    const blob = new Blob([img], { type: "image/jpeg" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
