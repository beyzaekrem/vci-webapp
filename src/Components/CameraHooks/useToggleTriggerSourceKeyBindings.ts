import { getServers, useParameter } from "../../network/capture-server";
import { useKeyPress } from "../../Utility/KeyBindings";
import { triggerSource as triggerSourceIcon } from "../Icons";


export function useToggleTriggerSourceKeyBindings(serverIndex: number, cameraIndex: number) {
    const camera = getServers().getServer(serverIndex).getCamera(cameraIndex);

    const x = useParameter(serverIndex, cameraIndex, (cam) => cam.trigger_source);
    const int_value = Number(x?.value?.value || -1);

    function refresh() {
        getServers().getServer(serverIndex).getAllInfo();
    }

    const triggerSources = {
        0: "Consecutive Frames",
        1: "Rising Edge",
        2: "Falling Edge",
        3: "Software Trigger",
        4: "High",
        5: "Low",
    };

    const current = (triggerSources as any)[int_value] || "Unknown";
    const display = [0, 3].includes(int_value) ? current + " (!)" : triggerSourceIcon;

    useKeyPress({
        key: "t",
        onKeyEvent: () => {
            if(int_value == 3) {
                camera.setParameter("trigger_source", 1).then(refresh);
            }
            else if(int_value == 1) {
                camera.setParameter("trigger_source", 3).then(refresh);
            }
            else if(int_value == 2) {
                camera.setParameter("trigger_source", 3).then(refresh);
            }
        },
        description: 'The current trigger source is "' + current + '". (Click to toggle)',
        category: "Camera",
        dependencies: [camera, x, int_value, serverIndex, cameraIndex],
        icon: display
    });
}
