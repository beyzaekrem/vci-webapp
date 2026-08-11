import { type KeyboardEvent as ReactKeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { Button, ButtonGroup, Form, InputGroup } from "react-bootstrap";
import { getVCI } from "../../../../network/vci-automation";
import type {
    AutomaticUserInputEvent,
    DisplayImageEvent,
    InputEvent,
    ManualUserInputEvent,
    ScriptEventResponseValue,
    UserBooleanInputEvent,
    UserInputEvent,
} from "../../../../network/vci-automation";

type UserInputLikeEvent = UserInputEvent | ManualUserInputEvent | AutomaticUserInputEvent;

type InteractionCommonProps = {
    disabled?: boolean;
    readonly?: boolean;
    onComplete?: () => void;
};

function useInteractionFocus<T extends HTMLElement>() {
    const interactionRef = useRef<T>(null);

    useEffect(() => {
        interactionRef.current?.focus();
    }, []);

    return interactionRef;
}

function getInputEvent(event: UserInputLikeEvent): InputEvent {
    return "input_event" in event ? event.input_event : event;
}

function isBooleanInputEvent(event: InputEvent): event is UserBooleanInputEvent {
    return event.type === "USER_BOOLEAN_INPUT";
}

export function DisplayImageInteraction({ event }: { event: DisplayImageEvent }) {
    return (
        <div>
            <p>{event.caption}</p>
            <img
                src={`data:image/png;base64,${event.image_data}`}
                alt={event.caption}
                style={{ maxWidth: "100%" }}
            />
        </div>
    );
}

export function UserBooleanInputInteraction({
    event,
    disabled,
    readonly,
    onComplete,
    headerContent,
    footerContent,
}: { event: UserBooleanInputEvent; headerContent?: ReactNode; footerContent?: ReactNode } & InteractionCommonProps) {
    const interactionRef = useInteractionFocus<HTMLDivElement>();
    const canSubmit = !disabled && !readonly && !!event.runner_id && !!event.event_id;

    const sendResponse = (response: boolean) => {
        if(!canSubmit) {
            console.warn("Cannot submit boolean response:", {
                runner_id: event.runner_id,
                event_id: event.event_id,
                disabled,
                readonly,
            });
            return;
        }

        getVCI().send_script_event_response(
            event.runner_id,
            event.event_id,
            response,
        );
        onComplete?.();
    };

    const handleKeyDown = (keyboardEvent: ReactKeyboardEvent<HTMLDivElement>) => {
        if(!canSubmit) return;

        if(keyboardEvent.key === "Enter") {
            keyboardEvent.preventDefault();
            keyboardEvent.stopPropagation();
            sendResponse(event.default_choice);
        }

        if(keyboardEvent.key === "Escape") {
            keyboardEvent.preventDefault();
            keyboardEvent.stopPropagation();
            sendResponse(!event.default_choice);
        }
    };

    return (
        <div
            ref={interactionRef}
            tabIndex={0}
            onKeyDown={handleKeyDown}
        >
            <p>{event.prompt}</p>
            {headerContent}
            <ButtonGroup>
                <Button
                    type="button"
                    disabled={!canSubmit}
                    variant={event.default_choice ? "primary" : "secondary"}
                    onClick={() => sendResponse(true)}
                >
                    Yes
                </Button>
                <Button
                    type="button"
                    disabled={!canSubmit}
                    variant={!event.default_choice ? "primary" : "secondary"}
                    onClick={() => sendResponse(false)}
                >
                    No
                </Button>
            </ButtonGroup>
            {footerContent}
        </div>
    );
}

export function UserInputInteraction({
    event,
    disabled,
    readonly,
    onComplete,
}: { event: UserInputLikeEvent } & InteractionCommonProps) {
    const inputEvent = getInputEvent(event);
    const inputRef = useInteractionFocus<HTMLInputElement>();
    const [inputValue, setInputValue] = useState(
        isBooleanInputEvent(inputEvent) ? "" : inputEvent.default_value ?? "",
    );
    const [remainingSeconds, setRemainingSeconds] = useState(
        event.type === "AUTOMATIC_USER_INPUT" ? event.timeout_seconds : null,
    );

    useEffect(() => {
        if(!isBooleanInputEvent(inputEvent)) {
            setInputValue(inputEvent.default_value ?? "");
        }
    }, [inputEvent, event.event_id]);

    useEffect(() => {
        if(event.type !== "AUTOMATIC_USER_INPUT") {
            setRemainingSeconds(null);
            return;
        }

        setRemainingSeconds(event.timeout_seconds);
        const startedAt = Date.now();
        const intervalId = window.setInterval(() => {
            const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
            setRemainingSeconds(Math.max(event.timeout_seconds - elapsedSeconds, 0));
        }, 250);

        return () => window.clearInterval(intervalId);
    }, [event]);

    const canSubmit = !disabled && !readonly && !!event.runner_id && !!event.event_id;

    const sendResponse = (response: ScriptEventResponseValue = inputValue) => {
        if(!canSubmit) {
            console.warn("Cannot submit response:", {
                runner_id: event.runner_id,
                event_id: event.event_id,
                disabled,
                readonly,
            });
            return;
        }

        getVCI().send_script_event_response(
            event.runner_id,
            event.event_id,
            response,
        );
        onComplete?.();
    };

    const switchModeLabel = event.type === "MANUAL_USER_INPUT"
        ? "Switch to automatic mode"
        : event.type === "AUTOMATIC_USER_INPUT"
            ? "Switch to manual mode"
            : null;

    const switchModeResponse = event.type === "MANUAL_USER_INPUT"
        ? "switch_to_auto"
        : event.type === "AUTOMATIC_USER_INPUT"
            ? "switch_to_manual"
            : null;

    const headerContent = event.type === "AUTOMATIC_USER_INPUT" && remainingSeconds !== null
        ? <p>Auto trigger in {remainingSeconds}s</p>
        : undefined;

    const footerContent = switchModeLabel && switchModeResponse
        ? (
            <Button
                type="button"
                variant="link"
                disabled={!canSubmit}
                onClick={() => sendResponse(switchModeResponse)}
            >
                {switchModeLabel}
            </Button>
        )
        : undefined;

    if(isBooleanInputEvent(inputEvent)) {
        return (
            <UserBooleanInputInteraction
                event={{
                    ...inputEvent,
                    runner_id: event.runner_id,
                    event_id: event.event_id,
                    timestamp: event.timestamp,
                    event_slot: event.event_slot,
                }}
                disabled={disabled}
                readonly={readonly}
                onComplete={onComplete}
                headerContent={headerContent}
                footerContent={footerContent}
            />
        );
    }

    return (
        <div>
            <p>{inputEvent.prompt}</p>
            {headerContent}
            <InputGroup>
                <Form.Control
                    ref={inputRef}
                    disabled={disabled || readonly}
                    value={inputValue}
                    onChange={(value) => setInputValue(value.currentTarget.value)}
                    onKeyDown={(event) => {
                        if(event.key !== "Enter") return;
                        event.preventDefault();
                        sendResponse();
                    }}
                />
                <Button
                    type="button"
                    disabled={!canSubmit}
                    onClick={() => sendResponse()}
                >
                    Submit
                </Button>
            </InputGroup>
            {footerContent}
        </div>
    );
}
