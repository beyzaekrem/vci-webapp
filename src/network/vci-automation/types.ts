export type ScriptEvent = {
    type: string;
    event_id: string;
    runner_id: string;
    timestamp: number;
    event_slot?: string;
};

export type LogEvent = ScriptEvent & {
    type: "LOG";
    content: string;
    log_level?: "info" | "debug" | "warning" | "error";
};

export type DisplayImageEvent = ScriptEvent & {
    type: "DISPLAY_IMAGE";
    image_data: string;
    caption: string;
};

export type UserBooleanInputEvent = ScriptEvent & {
    type: "USER_BOOLEAN_INPUT";
    prompt: string;
    default_choice: boolean;
};

export type UserBooleanInputEventWithResponse = Omit<UserBooleanInputEvent, "type"> & {
    type: "USER_BOOLEAN_INPUT_RESPONSE";
    user_response: boolean;
};

export type UserInputEvent = ScriptEvent & {
    type: "USER_INPUT";
    prompt: string;
    default_value?: string;
};

export type UserInputEventWithResponse = Omit<UserInputEvent, "type"> & {
    type: "USER_INPUT_RESPONSE";
    user_response: string | null;
};

export type InputEvent = UserBooleanInputEvent | UserInputEvent;
export type ScriptEventResponseValue = string | boolean | null;

export type ManualUserInputEvent = ScriptEvent & {
    type: "MANUAL_USER_INPUT";
    input_event: InputEvent;
};

export type AutomaticUserInputEvent = ScriptEvent & {
    type: "AUTOMATIC_USER_INPUT";
    input_event: InputEvent;
    timeout_seconds: number;
    timeout_return: ScriptEventResponseValue;
};

export type ManualUserInputEventWithResponse = Omit<ManualUserInputEvent, "type"> & {
    type: "MANUAL_USER_INPUT_RESPONSE";
    user_response: ScriptEventResponseValue;
    switch_mode: boolean;
};

export type AutomaticUserInputEventWithResponse = Omit<AutomaticUserInputEvent, "type"> & {
    type: "AUTOMATIC_USER_INPUT_RESPONSE";
    user_response: ScriptEventResponseValue;
    switch_mode: boolean;
    timed_out: boolean;
};

export type UserInputRequestEvent =
    | UserInputEvent
    | ManualUserInputEvent
    | AutomaticUserInputEvent;

export type UserInputResponseEvent =
    | UserInputEventWithResponse
    | ManualUserInputEventWithResponse
    | AutomaticUserInputEventWithResponse;

export type SupportedScriptEvent =
    | DisplayImageEvent
    | UserBooleanInputEvent
    | UserBooleanInputEventWithResponse
    | UserInputRequestEvent
    | UserInputResponseEvent;

export type SupportedScriptEventType = SupportedScriptEvent["type"];
