import { useEffect, useRef, useState } from "react";
import { largestRect } from "rect-scaler";
import { useClientSize } from "./useClientSize";
import { StreamWebsocket } from "./WebsocketStream";
import { SelectCameraModal, useCameraSelectionsReadOnly } from "../SelectCameras";
import { useIntegerZoomKeyBindingsWebsocket } from "./IntegerZoom/IntegerZoomMenu";
import { useExposureKeyBindings, useToggleTriggerSourceKeyBindings } from "../CameraHooks";
import { ContextMenu } from "../../Utility/KeyBindings";
import { useDownloadImage, useFullScreen } from "../CameraHooks";
import { useClientID } from "../../Utility/Storage";

interface ScalingResult {
    rows: number;
    cols: number;
    width: number;
    height: number;
}

interface GridLayoutProps {
    length: number;
    renderElement: (size: { width: number; height: number }, index: number) => JSX.Element;
}

/**
 * A reusable grid layout component that calculates the optimal grid size
 * and renders elements using the provided render function.
 */
export function GridLayout({ length, renderElement }: GridLayoutProps) {
    const gridRef = useRef<HTMLDivElement>(null);
    const gridSize = useClientSize(gridRef);
    const [defaultImageSize] = useState({ width: 5328, height: 4608 });
    const [scalingResult, setScalingResult] = useState<null | ScalingResult>(null);

    useEffect(() => {
        if(!gridRef.current) return;
        const rectResult = largestRect(
            gridSize.width,
            gridSize.height,
            length || 1,
            defaultImageSize.width,
            defaultImageSize.height
        );
        setScalingResult(rectResult);
    }, [gridSize, defaultImageSize, length]);

    return (
        <div ref={gridRef} style={{ width: "100%", height: "100%" }}>
            {scalingResult && (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: `repeat(${scalingResult.cols}, 1fr)`,
                        gridTemplateRows: `repeat(${scalingResult.rows}, 1fr)`,
                        gap: "0px",
                    }}
                >
                    {Array.from({ length }).map((_, index) => (
                        <div
                            key={index}
                            style={{ width: scalingResult.width, height: scalingResult.height, backgroundColor: "#f3f3f3" }}
                        >
                            {renderElement({ width: scalingResult.width, height: scalingResult.height }, index)}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

interface StreamIndexProps {
    serverIndex: number;
    cameraIndex: number;
    streamID: string;
}

/**
 * Shows the websocket livestreams of the cameras in a grid that maximizes the use of the screen.
 */
export function Grid({ streams }: { streams: StreamIndexProps[] }) {
    return (
        <GridLayout
            length={streams.length}
            renderElement={({ width, height }, index) => (
                <>
                    <StreamWebsocket
                        autoStart={true}
                        cameraIndex={streams[index].cameraIndex}
                        serverIndex={streams[index].serverIndex}
                        width={width}
                        height={height}
                        constantStreamID={streams[index].streamID}
                    />
                </>
            )}
        />
    );
}


/**
 * Shows the grid of cameras selected in the url query parameters (selectionKey = "camerasInGrid")
 * @returns A grid of the cameras selected in the url query parameters
 */
export function GridFromQueryParam() {
    const storage = "url";
    const selectionKey = "camerasInGrid";
    const cameras = useCameraSelectionsReadOnly({ storage, selectionKey });

    const clientID = useClientID();

    const streams = cameras.map((camera, index) => {
        return {
            serverIndex: camera.server,
            cameraIndex: camera.camera,
            streamID: "grid" + camera.camera + "_" + clientID
        }
    })


    return <>
        <SelectCameraModal keyToOpen="s" selectionKey={selectionKey} storage={storage} isMulti />
        <Grid streams={streams} />
    </>

}

export function GridWithFocusedElement({ streams }: { streams: StreamIndexProps[] }) {
    const [focusedCamera, setFocusedCamera] = useState(0);

    const currentCamera = streams.length > 0 ? streams[focusedCamera] : { serverIndex: 0, cameraIndex: 0, streamID: "grid0" };

    useIntegerZoomKeyBindingsWebsocket(currentCamera.streamID, currentCamera.serverIndex);

    useExposureKeyBindings(currentCamera.serverIndex, currentCamera.cameraIndex);

    useDownloadImage(currentCamera.serverIndex, currentCamera.cameraIndex);

    useFullScreen(currentCamera.serverIndex, currentCamera.cameraIndex);

    useToggleTriggerSourceKeyBindings(currentCamera.serverIndex, currentCamera.cameraIndex);

    return (
        <GridLayout
            length={streams.length}
            renderElement={({ width, height }, index) => (
                <div style={{
                    outline: focusedCamera == index ? "5px solid var(--bs-primary)" : "",
                    zIndex: focusedCamera == index ? 2 : 1,
                    position: "relative",
                    width: width,
                    height: height,
                }} onClick={() => setFocusedCamera(index)}>
                    {
                        focusedCamera == index &&
                        <div style={{ position: "absolute", top: 0, left: 0, width: "100%" }}>
                            <ContextMenu category="Camera" />
                            <ContextMenu category="Integer Zoom" />
                        </div>
                    }
                    <StreamWebsocket
                        autoStart={true}
                        cameraIndex={streams[index].cameraIndex}
                        serverIndex={streams[index].serverIndex}
                        width={width}
                        height={height}
                        constantStreamID={streams[index].streamID}
                    />
                </div>
            )}
        />
    );
}