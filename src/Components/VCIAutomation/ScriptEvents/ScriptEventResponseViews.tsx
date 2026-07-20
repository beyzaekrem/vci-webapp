import type {
    InputEvent,
    ScriptEventResponseValue,
    UserBooleanInputEventWithResponse,
    UserInputResponseEvent,
} from "../../../network/vci-automation";

function getPrompt(event: UserInputResponseEvent) {
    return "input_event" in event ? event.input_event.prompt : event.prompt;
}

function formatResponseValue(value: ScriptEventResponseValue, inputEvent?: InputEvent) {
    if(typeof value === "boolean") {
        return value ? "Yes" : "No";
    }

    if(value === null) {
        return "";
    }

    if(inputEvent?.type === "USER_BOOLEAN_INPUT") {
        if(value === "true") return "Yes";
        if(value === "false") return "No";
    }

    return value;
}

export function UserBooleanInputResponseView({ event }: { event: UserBooleanInputEventWithResponse }) {
    return (
        <div>
            <p>{event.prompt}</p>
            <p>You selected: {event.user_response ? "Yes" : "No"}</p>
        </div>
    );
}

export function UserInputResponseView({ event }: { event: UserInputResponseEvent }) {
    const timedOut = "timed_out" in event ? event.timed_out : false;
    const switchMode = "switch_mode" in event ? event.switch_mode : false;
    const inputEvent = "input_event" in event ? event.input_event : undefined;
    const responseLabel = inputEvent?.type === "USER_BOOLEAN_INPUT" ? "You selected:" : "You entered:";

    return (
        <div>
            <p>{getPrompt(event)}</p>
            <p>{responseLabel} {formatResponseValue(event.user_response, inputEvent)}</p>
            {timedOut && <p>Response was returned by timeout.</p>}
            {switchMode && <p>Mode switch requested.</p>}
        </div>
    );
}
