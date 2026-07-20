import { useKeyPress } from "../../Utility/KeyBindings";
import { getServers } from "../../network/capture-server";
import { downloadIcon } from "../Icons";

export function useDownloadImage(serverIndex: number, cameraIndex: number) {
    useKeyPress({
        key: "c",
        onKeyEvent: () => {
            getServers()
                .getServer(serverIndex)
                .getCamera(cameraIndex)
                .downloadImage();
        },
        description: "Download Full Resolution Image",
        category: "Camera",
        icon: downloadIcon,
        dependencies: [serverIndex, cameraIndex],
    });
}


