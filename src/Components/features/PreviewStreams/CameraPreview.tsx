import { useRef, useMemo } from "react";
import { ChevronLeft, ChevronRight, Camera, RefreshCw, Maximize2, Plus } from "lucide-react";
import { StreamWebsocket } from "../../Videostream/WebsocketStream";
import { useClientSize } from "../../Videostream/useClientSize";
import { getServers } from "../../../network/capture-server";
import {
    getSlotDisplayName,
    type CameraEntry,
    type ResolvedCamera,
} from "./systemLayoutData";

interface CameraPreviewProps {
    selectedCamera?: ResolvedCamera | null;
    camera?: ResolvedCamera | null;
    cameraEntry?: CameraEntry | null;
    allResolvedCameras?: ResolvedCamera[];
    onNavigate?: (direction: -1 | 1) => void;
    streamID: string;
}

export function CameraPreview({
    selectedCamera,
    camera,
    cameraEntry,
    allResolvedCameras = [],
    onNavigate,
    streamID,
}: CameraPreviewProps) {
    const bodyRef = useRef<HTMLDivElement>(null);
    const bodySize = useClientSize(bodyRef);

    const activeCamera = selectedCamera || camera || null;
    const activeEntry = cameraEntry || activeCamera;
    const safeCameras = allResolvedCameras || [];

    const currentIndex = activeCamera
        ? safeCameras.findIndex(
            (c) => c.shorthand === activeCamera.shorthand && c.pillarKey === activeCamera.pillarKey,
        )
        : -1;
    const totalCameras = safeCameras.length;

    // Display title formatted as in screenshot e.g. "Camera 03 - Center Rig"
    const cameraDisplayName = useMemo(() => {
        if (!activeEntry) return "No Camera Selected";
        const camName = activeEntry.shorthand;
        const slotName = getSlotDisplayName(activeEntry.slot);
        return `Camera ${camName} - ${slotName}`;
    }, [activeEntry]);

    function handleDownload() {
        if (!activeCamera) return;
        getServers().getServer(activeCamera.serverIndex)?.getCamera(activeCamera.cameraIndex)?.downloadImage();
    }

    function handleFullscreen() {
        if (!activeCamera) return;
        window.open(`/#/videostream?camerasInGrid=${activeCamera.serverIndex}-${activeCamera.cameraIndex}`, "_blank");
    }

    function handleRefresh() {
        if (!activeCamera) return;
        getServers().getServer(activeCamera.serverIndex)?.getAllInfo();
    }

    const camFormattedIndex = currentIndex >= 0 ? String(currentIndex + 1).padStart(2, "0") : "01";
    const totalFormatted = String(totalCameras).padStart(2, "0");

    return (
        <div className="ps-preview-card">
            {/* Header */}
            <div className="ps-preview-header">
                <div className="ps-preview-header-left">
                    <span className="ps-live-indicator">
                        <span className="ps-live-dot-pulse" />
                        LIVE
                    </span>
                    <span className="ps-camera-title">{cameraDisplayName}</span>
                </div>

                <div className="ps-preview-nav">
                    <button
                        className="ps-nav-arrow"
                        onClick={() => onNavigate?.(-1)}
                        disabled={totalCameras === 0}
                        title="Previous camera"
                    >
                        <ChevronLeft size={16} />
                    </button>
                    <span>Cam {camFormattedIndex} / {totalFormatted}</span>
                    <button
                        className="ps-nav-arrow"
                        onClick={() => onNavigate?.(1)}
                        disabled={totalCameras === 0}
                        title="Next camera"
                    >
                        <ChevronRight size={16} />
                    </button>
                </div>
            </div>

            {/* Video Body Viewport */}
            <div className="ps-preview-body" ref={bodyRef}>
                {/* Center Crosshair Overlay */}
                <div className="ps-crosshair">
                    <Plus size={36} strokeWidth={1} />
                </div>

                {activeCamera ? (
                    <StreamWebsocket
                        serverIndex={activeCamera.serverIndex}
                        cameraIndex={activeCamera.cameraIndex}
                        width={bodySize.width || 800}
                        height={bodySize.height || 600}
                        constantStreamID={streamID}
                        autoStart={true}
                    />
                ) : (
                    <div className="ps-preview-empty">
                        <span>Select a camera from the Spatial Map</span>
                    </div>
                )}
            </div>

            {/* Footer Overlay */}
            <div className="ps-preview-footer">
                <div className="ps-stream-badge">
                    1920×1080 • 30 FPS • H.264
                </div>

                <div className="ps-action-group">
                    <button
                        className="ps-action-btn"
                        onClick={handleDownload}
                        disabled={!activeCamera}
                        title="Snapshot / Download"
                    >
                        <Camera size={16} />
                    </button>
                    <button
                        className="ps-action-btn"
                        onClick={handleRefresh}
                        disabled={!activeCamera}
                        title="Refresh"
                    >
                        <RefreshCw size={16} />
                    </button>
                    <button
                        className="ps-action-btn"
                        onClick={handleFullscreen}
                        disabled={!activeCamera}
                        title="Fullscreen"
                    >
                        <Maximize2 size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
}
