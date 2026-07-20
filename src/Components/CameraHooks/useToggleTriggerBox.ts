import { useControlServerAddress } from "../../network/control-server";
import { useKeyPress } from "../../Utility/KeyBindings";

/**
 * Hook to toggle the trigger box on using a key press.
 *
 * @remarks
 * - //TODO currently, we only set the trigger box to "on", since there is no way to request its current state. (or is there?)
 *
 * @example
 * ```typescript
 * useToggleTriggerBox();
 * ```
 */

export function useToggleTriggerBox() {
    const [controlServerAddress] = useControlServerAddress();

    useKeyPress({
        key: "T",
        onKeyEvent: () => {
            //TODO implement this as a method in the ControlServer class instead
            fetch(`http://${controlServerAddress}:8080/on`).then(response => {
                if(response.ok) {
                    console.log("Trigger Box On");
                } else {
                    console.error("Failed to trigger box on");
                }
            });
        },
        description: 'Trigger Box On',
        category: "Camera",
        icon: "Trigger Box On",
        dependencies: [controlServerAddress]
    });
}
