import { getServers } from "../../network/capture-server";
import { useKeyPress } from "../../Utility/KeyBindings";
import { exposureIconPlus, exposureIconMinus } from "../Icons";

export function useExposureKeyBindings(serverIndex: number, cameraIndex: number) {
    const server = getServers().getServer(serverIndex);
    const camera = server ? server.getCamera(cameraIndex) : undefined;

    useKeyPress({
        key: "NumpadAdd",
        onKeyEvent: () => {
            camera?.setParameterIncremental("exposure", 5000);
        },
        description: "Increase Exposure",
        category: "Camera",
        icon: exposureIconPlus,
        dependencies: [camera],
    });

    useKeyPress({
        key: "NumpadSubtract",
        onKeyEvent: () => {
            camera?.setParameterIncremental("exposure", -5000);
        },
        description: "Decrease Exposure",
        category: "Camera",
        icon: exposureIconMinus,
        dependencies: [camera],
    });
}

