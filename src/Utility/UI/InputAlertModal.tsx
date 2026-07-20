import { useCallback, useEffect, useState, type ComponentProps } from "react";
import { Button, Form, Modal } from "react-bootstrap";

/**
 * Props for the input alert modal component.
 */
export type InputAlertModalProps = {
    /** Title shown in the modal header. */
    title: string | JSX.Element;
    /** Prompt content shown above the input. */
    message: string | JSX.Element;
    /** Optional callback fired when the user confirms with their input value. */
    onAccept?: (value: string) => void;
    /** Optional callback fired when the modal closes/cancels. */
    onClose?: () => void;
    /** Whether the modal is currently visible. */
    show?: boolean;
    /** Setter for controlling the visible state externally. */
    setShow?: (show: boolean) => void;
    /** Whether to show the cancel button. */
    showCancel?: boolean;
    /** Optional override for modal props (size, centered, etc). */
    modalProps?: Partial<ComponentProps<typeof Modal>>;
    /** Optional override for input props (placeholder, type, etc). */
    inputProps?: Partial<ComponentProps<typeof Form.Control>>;
    okButtonText?: string | JSX.Element;
    cancelButtonText?: string | JSX.Element;
    /** Initial value shown in the input whenever the modal opens. */
    initialValue?: string;
    /** Placeholder shown when the input is empty. */
    placeholder?: string;
    /** Whether empty values can be submitted. */
    allowEmpty?: boolean;
    /** Whether to render a textarea instead of a single-line input. */
    multiline?: boolean;
};

/**
 * Renders a modal that prompts the user for text input.
 * @returns Modal element with Cancel/Ok actions.
 */
export function InputAlertModal({
    title,
    message,
    onAccept,
    onClose,
    show,
    setShow,
    showCancel = true,
    modalProps,
    inputProps,
    okButtonText,
    cancelButtonText,
    initialValue = "",
    placeholder,
    allowEmpty = true,
    multiline = false,
}: InputAlertModalProps) {
    const [value, setValue] = useState(initialValue);

    useEffect(() => {
        if(show) setValue(initialValue);
    }, [show, initialValue]);

    const handleAccept = useCallback(() => {
        if(!allowEmpty && value.trim() === "") return;
        if(setShow) setShow(false);
        if(onAccept) onAccept(value);
    }, [allowEmpty, onAccept, setShow, value]);

    const handleHide = useCallback(() => {
        if(setShow) setShow(false);
        if(onClose) onClose();
    }, [setShow, onClose]);

    const handleSubmit = useCallback((e: React.FormEvent) => {
        e.preventDefault();
        handleAccept();
    }, [handleAccept]);

    const canSubmit = allowEmpty || value.trim() !== "";

    return (
        <Modal {...modalProps} show={!!show} onHide={handleHide} backdrop={true} keyboard={true}>
            <Modal.Header closeButton>
                <Modal.Title>{title}</Modal.Title>
            </Modal.Header>
            <Form onSubmit={handleSubmit}>
                <Modal.Body>
                    <div style={{ marginBottom: "0.75rem" }}>{message}</div>
                    <Form.Control
                        {...inputProps}
                        autoFocus
                        as={multiline ? "textarea" : inputProps?.as}
                        rows={multiline ? inputProps?.rows || 3 : inputProps?.rows}
                        value={value}
                        placeholder={placeholder}
                        onChange={(e) => setValue(e.currentTarget.value)}
                    />
                </Modal.Body>
                <Modal.Footer style={{ justifyContent: "space-between" }}>
                    {showCancel ? (
                        <Button variant="secondary" onClick={handleHide}>
                            {cancelButtonText || "Cancel"}
                        </Button>
                    ) : null}
                    <Button variant="primary" type="submit" disabled={!canSubmit}>
                        {okButtonText || "Ok"}
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
}

/**
 * Props for the input alert modal launcher button.
 */
type InputAlertModalButtonProps = {
    /** Button label shown to open the modal. */
    buttonText: string | JSX.Element;
    /** Props forwarded to the trigger button. */
    buttonProps?: Partial<ComponentProps<typeof Button>>;
} & Omit<InputAlertModalProps, "show" | "setShow">;

/**
 * Renders a button that opens an input alert modal.
 * @returns Button and modal elements bound to internal state.
 */
export function InputAlertModalButton({ buttonText, ...props }: InputAlertModalButtonProps) {
    const [show, setShow] = useState(false);
    return <>
        <InputAlertModal {...props} show={show} setShow={setShow} />
        <Button variant="primary" {...props.buttonProps} onClick={() => setShow(true)}>
            {buttonText}
        </Button>
    </>
}

/**
 * Returns a component and function to display an input alert modal and wait for user response.
 */
export function useDisplayInputAlertModal() {
    const [show, setShow] = useState(false);
    const [propsToDisplay, setPropsToDisplay] = useState<InputAlertModalProps | null>(null);

    const displayAndWaitForResponse = useCallback((props: Omit<InputAlertModalProps, "show" | "setShow">) => {
        return new Promise<string | null>((resolve) => {
            setPropsToDisplay({
                ...props,
                onAccept: (value) => {
                    setShow(false);
                    resolve(value);
                },
                onClose: () => {
                    setShow(false);
                    resolve(null);
                },
            });
            setShow(true);
        });
    }, []);

    const cancel = useCallback(() => {
        setShow(false);
    }, []);

    const ModalComponent = propsToDisplay && <InputAlertModal {...propsToDisplay} show={show} setShow={setShow} />;
    return [ModalComponent, displayAndWaitForResponse, cancel] as const;
}
