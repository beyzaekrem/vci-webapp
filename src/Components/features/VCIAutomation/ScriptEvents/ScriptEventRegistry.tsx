import type { AlertModalProps } from "../../../../Utility/UI";
import type {
    ScriptEvent,
    SupportedScriptEvent,
    SupportedScriptEventType,
} from "../../../../network/vci-automation";
import {
    DisplayImageInteraction,
    UserBooleanInputInteraction,
    UserInputInteraction,
} from "./ScriptEventInteractions";
import {
    UserBooleanInputResponseView,
    UserInputResponseView,
} from "./ScriptEventResponseViews";

export type ScriptEventRenderProps = {
    event: SupportedScriptEvent;
    disabled?: boolean;
    readonly?: boolean;
    onComplete?: () => void;
};

type ScriptEventKind = "display" | "request" | "response";

type ScriptEventDefinition<TEvent extends SupportedScriptEvent = SupportedScriptEvent> = {
    kind: ScriptEventKind;
    highlight?: boolean;
    render: (props: {
        event: TEvent;
        disabled?: boolean;
        readonly?: boolean;
        onComplete?: () => void;
    }) => JSX.Element;
    getModalProps?: (
        event: TEvent,
        onComplete: () => void,
    ) => Omit<AlertModalProps, "show" | "setShow"> | null;
};

type ScriptEventRegistry = {
    [TType in SupportedScriptEventType]: ScriptEventDefinition<Extract<SupportedScriptEvent, { type: TType }>>;
};

function createRequestModalProps<TEvent extends SupportedScriptEvent>(
    render: ScriptEventDefinition<TEvent>["render"],
) {
    return (event: TEvent, onComplete: () => void): Omit<AlertModalProps, "show" | "setShow"> => ({
        title: "Script Request",
        hideFooter: true,
        modalProps: {
            backdrop: "static",
        },
        message: render({ event, onComplete }),
    });
}

export const scriptEventRegistry: ScriptEventRegistry = {
    DISPLAY_IMAGE: {
        kind: "display",
        render: ({ event }) => <DisplayImageInteraction event={event} />,
        getModalProps: (event) => ({
            title: event.caption,
            okButtonText: "Close",
            showCancel: false,
            message: <DisplayImageInteraction event={event} />,
        }),
    },
    USER_BOOLEAN_INPUT: {
        kind: "request",
        highlight: true,
        render: ({ event, disabled, readonly, onComplete }) => (
            <UserBooleanInputInteraction
                event={event}
                disabled={disabled}
                readonly={readonly}
                onComplete={onComplete}
            />
        ),
        getModalProps: createRequestModalProps(({ event, onComplete }) => (
            <UserBooleanInputInteraction event={event} onComplete={onComplete} />
        )),
    },
    USER_BOOLEAN_INPUT_RESPONSE: {
        kind: "response",
        render: ({ event }) => <UserBooleanInputResponseView event={event} />,
    },
    USER_INPUT: {
        kind: "request",
        highlight: true,
        render: ({ event, disabled, readonly, onComplete }) => (
            <UserInputInteraction
                event={event}
                disabled={disabled}
                readonly={readonly}
                onComplete={onComplete}
            />
        ),
        getModalProps: createRequestModalProps(({ event, onComplete }) => (
            <UserInputInteraction event={event} onComplete={onComplete} />
        )),
    },
    USER_INPUT_RESPONSE: {
        kind: "response",
        render: ({ event }) => <UserInputResponseView event={event} />,
    },
    MANUAL_USER_INPUT: {
        kind: "request",
        highlight: true,
        render: ({ event, disabled, readonly, onComplete }) => (
            <UserInputInteraction
                event={event}
                disabled={disabled}
                readonly={readonly}
                onComplete={onComplete}
            />
        ),
        getModalProps: createRequestModalProps(({ event, onComplete }) => (
            <UserInputInteraction event={event} onComplete={onComplete} />
        )),
    },
    MANUAL_USER_INPUT_RESPONSE: {
        kind: "response",
        render: ({ event }) => <UserInputResponseView event={event} />,
    },
    AUTOMATIC_USER_INPUT: {
        kind: "request",
        highlight: true,
        render: ({ event, disabled, readonly, onComplete }) => (
            <UserInputInteraction
                event={event}
                disabled={disabled}
                readonly={readonly}
                onComplete={onComplete}
            />
        ),
        getModalProps: createRequestModalProps(({ event, onComplete }) => (
            <UserInputInteraction event={event} onComplete={onComplete} />
        )),
    },
    AUTOMATIC_USER_INPUT_RESPONSE: {
        kind: "response",
        render: ({ event }) => <UserInputResponseView event={event} />,
    },
};

export function isSupportedScriptEventType(value: string): value is SupportedScriptEventType {
    return value in scriptEventRegistry;
}

export function isSupportedScriptEvent(value: unknown): value is SupportedScriptEvent {
    if(typeof value !== "object" || value === null) {
        return false;
    }

    const eventType = (value as { type?: unknown }).type;
    return typeof eventType === "string" && isSupportedScriptEventType(eventType);
}

export function getScriptEventDefinition(event: SupportedScriptEvent) {
    return scriptEventRegistry[event.type] as ScriptEventDefinition<SupportedScriptEvent>;
}

export function isScriptInteractionResponse(event: ScriptEvent) {
    return isSupportedScriptEvent(event) && getScriptEventDefinition(event).kind === "response";
}
