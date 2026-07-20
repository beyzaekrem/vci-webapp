import { useKeyPress } from "../../Utility/KeyBindings";
import { fullscreenIcon } from "../Icons";


export function useFullScreen(serverIndex: number, cameraIndex: number) {
    useKeyPress({
        key: "f",
        onKeyEvent: () => {
            window.open(
                "/#/videostream?camerasInGrid=" + serverIndex + "-" + cameraIndex + "",
                "_blank"
            );
        },
        description: "Fullscreen",
        category: "Camera",
        icon: fullscreenIcon,
        dependencies: [serverIndex, cameraIndex],
    });
}
