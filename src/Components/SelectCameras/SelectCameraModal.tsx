import { useState } from "react";
import { useKeyPress } from "../../Utility/KeyBindings";
import { SelectCameras, SelectionProps } from "./SelectCameras";
import { AlertModal } from "../../Utility/UI";


/**
 * Displays a modal dialog for selecting one or more cameras.
 *
 * The `SelectCameraModal` component renders a modal that allows users to select one or more cameras.
 * The modal is triggered to open when the specified keyboard key (`keyToOpen`) is pressed.
 *
 * @param props - Component props.
 * @param props.keyToOpen - The keyboard key that opens the modal when pressed.
 * @param props.isMulti - If true, enables multi-selection of cameras.
 * @param props.storage - The storage mechanism or identifier for camera selection state.
 * @param props.selectionKey - A unique key for managing the selection state.
 *
 * @remarks
 * - Uses the `useKeyPress` hook to listen for the specified key event.
 * - Renders a `SelectCameras` component inside the modal body.
 * - The modal can be closed by clicking the close button or the "Close" footer button.
 */
export function SelectCameraModal(props: SelectionProps & { keyToOpen: string }) {
    const [show, setShow] = useState(false);

    useKeyPress({
        key: props.keyToOpen,
        description: "Open Camera Selection Modal",
        onKeyEvent: () => setShow(true),
        category: "General",
        icon: null,
        dependencies: [],
    });

    return (
        <AlertModal
            title="Select Cameras"
            message={
                <SelectCameras
                    isMulti={props.isMulti}
                    storage={props.storage}
                    selectionKey={props.selectionKey}
                />
            }
            show={show}
            setShow={setShow}
        />
    );
}
