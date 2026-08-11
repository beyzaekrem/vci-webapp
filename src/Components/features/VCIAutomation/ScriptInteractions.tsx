import { useEffect } from "react";
import { useDisplayAlertModal } from "../../../Utility/UI";
import { getVCI } from "../../../network/vci-automation";
import type { ScriptEvent } from "../../../network/vci-automation";
import {
    getScriptEventModalProps,
    isNonInteractionScriptEvent,
    isScriptInteractionResponse,
} from "./ScriptEvents";

export function ScriptInteractions({ runnerId }: { runnerId: string }) {
    const [AlertModal, displayAlert, closeAlert] = useDisplayAlertModal();

    useEffect(() => {
        const removeListener = getVCI().add_listener_output(runnerId, (message) => {
            // we assume the last event in the event history is the one that triggered the output update
            /*
            this works the same as subscribing to the script events,
            and also works in 95% of cases when you refresh the page inbetween and interactions will reappear.
            However:
            this does not work if we get a non-blocking event and then refresh the page,
            the event will not reappear after refresh even if we did not press ok on the alert yet.
            e.g. if we have a display image event, then a log shortly after.
            While we are not refreshing, the image will be displayed normally,
            but if we refresh while the image is displayed,
            the image will not be there after the refresh because the log is the last one.
            If we wanted to fix that, we should make the image event blocking/
            model that we have to acknowledge it more explicitely
            */
            const msg: ScriptEvent = message.full_event_history[message.full_event_history.length - 1];
            if(msg.event_slot !== undefined && msg.event_slot !== null) {
                return;
            }
            if(isScriptInteractionResponse(msg)) {
                closeAlert();
                return;
            }
            const modalProps = getScriptEventModalProps(msg, closeAlert);
            if(modalProps) {
                displayAlert(modalProps);
                return;
            }

            if(!isNonInteractionScriptEvent(msg)) {
                console.warn("Received unsupported event type for user interaction:", msg.type);
            }
        });
        return () => {
            removeListener();
        };
    }, [closeAlert, displayAlert, runnerId]);

    return <div>{AlertModal}</div>;
}
