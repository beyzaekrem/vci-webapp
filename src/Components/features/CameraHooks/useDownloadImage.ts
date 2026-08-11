import { useKeyPress } from "../../../Utility/KeyBindings";
import { getServers } from "../../../network/capture-server";
import { downloadIcon } from "../../shared/Icons";

export function useDownloadImage(serverIndex: number, cameraIndex: number) {
    useKeyPress({
        key: "c",
        onKeyEvent: () => {
            getServers()
                .getServer(serverIndex)
                ?.getCamera(cameraIndex)
                ?.downloadImage();
        },
        description: "Download Full Resolution Image",
        category: "Camera",
        icon: downloadIcon,
        dependencies: [serverIndex, cameraIndex],
    });
}



