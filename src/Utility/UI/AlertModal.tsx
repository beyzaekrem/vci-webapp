import { useCallback, useEffect, useRef, useState, type ComponentProps } from "react";
import { Button, Modal } from "react-bootstrap";

/**
 * Props for the alert modal component.
 */
export type AlertModalProps = {
    /** Title shown in the modal header. */
    title: string | JSX.Element;
    /** Message content shown in the modal body. */
    message: string | JSX.Element;
    /** Optional callback fired when the user confirms. */
    onAccept?: () => void;
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
    okButtonText?: string | JSX.Element;
    cancelButtonText?: string | JSX.Element;
    /** Which boolean choice should be treated as the default action. */
    defaultChoice?: boolean;
    /** Whether to hide the modal footer entirely. */
    hideFooter?: boolean;
};

/**
 * Renders a confirmation-style alert modal.
 * @param title Title shown in the modal header.
 * @param message Message content shown in the modal body.
 * @param onAccept Callback fired when the user confirms.
 * @param onClose Callback fired when the modal closes/cancels.
 * @param show Whether the modal is currently visible.
 * @param setShow Setter for controlling the visible state.
 * @returns Modal element with Cancel/Ok actions.
 */
export function AlertModal({
    title,
    message,
    onAccept,
    onClose,
    show,
    setShow,
    showCancel = true,
    okButtonText,
    cancelButtonText,
    modalProps,
    defaultChoice = true,
    hideFooter = false,
}: AlertModalProps) {
    const handleAccept = useCallback(() => {
        if(setShow) setShow(false);
        if(onAccept) onAccept();
    }, [setShow, onAccept]);

    const handleHide = useCallback(() => {
        if(setShow) setShow(false);
        if(onClose) onClose();
    }, [setShow, onClose]);

    useEffect(() => {
        if(!show) return;
        const handler = (e: KeyboardEvent) => {
            const target = e.target as HTMLElement | null;
            // ignore Enter when typing in inputs/textareas or contentEditable elements
            if(e.key === "Enter") {
                if(hideFooter) {
                    return;
                }
                if(target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
                    return;
                }
                e.preventDefault();
                if(defaultChoice || !showCancel) {
                    handleAccept();
                } else {
                    handleHide();
                }
            } else if(e.key === "Escape") {
                handleHide();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [show, defaultChoice, hideFooter, showCancel, handleAccept, handleHide]);

    const acceptButton = hideFooter ? null : (
        <Button
            variant={defaultChoice || !showCancel ? "primary" : "secondary"}
            onClick={handleAccept}
        >
            {okButtonText || "Ok"}
        </Button>
    );

    const cancelButton = hideFooter || !showCancel ? null : (
        <Button
            variant={!defaultChoice ? "primary" : "secondary"}
            onClick={handleHide}
        >
            {cancelButtonText || "Cancel"}
        </Button>
    );

    return (
        <Modal show={!!show} onHide={handleHide} backdrop={true} keyboard={true} {...modalProps}>
            <Modal.Header closeButton>
                <Modal.Title>{title}</Modal.Title>
            </Modal.Header>
            <Modal.Body>{message}</Modal.Body>
            {!hideFooter && (
                <Modal.Footer style={{ justifyContent: "space-between" }}>
                    {defaultChoice || !showCancel ? <>
                        {cancelButton}
                        {acceptButton}
                    </> : <>
                        {acceptButton}
                        {cancelButton}
                    </>}
                </Modal.Footer>
            )}
        </Modal>
    );
}

/**
 * Props for the alert modal launcher button.
 */
type AlertModalButtonProps = {
    /** Button label shown to open the modal. */
    buttonText: string | JSX.Element;
    /** Props forwarded to the trigger button. */
    buttonProps?: Partial<React.ComponentProps<typeof Button>>;
} & Omit<AlertModalProps, "show" | "setShow">;

/**
 * Renders a button that opens an alert modal.
 * @param buttonText Label content for the trigger button.
 * @param props Modal props forwarded to the alert modal component.
 * @returns Button and modal elements bound to internal state.
 */
export function AlertModalButton({ buttonText, ...props }: AlertModalButtonProps) {
    const [show, setShow] = useState(false);
    return <>
        <AlertModal {...props} show={show} setShow={setShow} />
        <Button variant="danger" {...props.buttonProps} onClick={() => setShow(true)}>
            {buttonText}
        </Button>
    </>
}


/**
 * Returns a component and function to display an alert modal and wait for user response.
 */
export function useDisplayAlertModal() {
    const [show, setShow] = useState(false);
    const [propsToDisplay, setPropsToDisplay] = useState<AlertModalProps | null>(null);
    const pendingResolve = useRef<((value: boolean) => void) | null>(null);

    const resolveAndClose = useCallback((value: boolean) => {
        setShow(false);
        pendingResolve.current?.(value);
        pendingResolve.current = null;
    }, []);

    const closeAlert = useCallback(() => {
        resolveAndClose(false);
    }, [resolveAndClose]);

    const displayAndWaitForResponse = useCallback((props: Omit<AlertModalProps, "show" | "setShow">) => {
        return new Promise<boolean>((resolve) => {
            pendingResolve.current = resolve;
            setPropsToDisplay({
                ...props,
                onAccept: () => {
                    resolveAndClose(true);
                },
                onClose: () => {
                    resolveAndClose(false);
                },
            });
            setShow(true);
        });
    }, [resolveAndClose]);

    const ModalComponent = propsToDisplay && <AlertModal {...propsToDisplay} show={show} setShow={setShow} />;
    return [ModalComponent, displayAndWaitForResponse, closeAlert] as const;
}
