import { useState, useMemo, useCallback, useEffect } from "react";
import { StageSpatialMap } from "./StageSpatialMap";
import { ServerFilters } from "./ServerFilters";
import { CameraPreview } from "./CameraPreview";
import {
    getAllCamerasFromLayout,
    buildShorthandMap,
    resolveCamera,
    type CameraEntry,
    type ResolvedCamera,
} from "./systemLayoutData";
import { useClientID } from "../../../Utility/Storage";
import { getServers, useCameraIndices } from "../../../network/capture-server";
import { ServerStatusButton } from "../../shared/ServerStatusModal";
import { ChevronDown, Map } from "lucide-react";
import "./previewStreams.css";

export function PreviewStreamsPage() {
    const cameraIndices = useCameraIndices();

    const resolvedMap = useMemo(() => buildShorthandMap(), [cameraIndices]);

    const allResolvedCameras = useMemo(() => {
        return getAllCamerasFromLayout()
            .map((e) => resolveCamera(e, resolvedMap))
            .filter((c): c is ResolvedCamera => c !== undefined);
    }, [resolvedMap]);

    const [selectedCamera, setSelectedCamera] = useState<CameraEntry | null>(null);
    const [selectedServer, setSelectedServer] = useState<number | null>(null);
    const [mobileMapOpen, setMobileMapOpen] = useState(false);

    const clientID = useClientID();

    const resolvedSelected = useMemo<ResolvedCamera | null>(() => {
        if (!selectedCamera) return null;
        const match = resolvedMap.get(selectedCamera.shorthand);
        if (!match) return null;
        return { ...selectedCamera, ...match };
    }, [selectedCamera, resolvedMap]);

    const streamID = useMemo(() => {
        if (!resolvedSelected) return "";
        return `previewStream_${resolvedSelected.shorthand}_${clientID}`;
    }, [resolvedSelected, clientID]);

    useEffect(() => {
        if (!resolvedSelected) return;
        const server = getServers().getServer(resolvedSelected.serverIndex);
        server?.switchMode("livestream");
    }, [resolvedSelected?.serverIndex]);

    useEffect(() => {
        if (!selectedCamera && allResolvedCameras.length > 0) {
            const first = allResolvedCameras[0];
            setSelectedCamera(first);
        }
    }, [allResolvedCameras, selectedCamera]);

    // On mobile, auto-close the map panel when a camera is selected
    const handleMobileCameraSelect = useCallback(
        (camera: CameraEntry) => {
            setSelectedCamera(camera);
            setMobileMapOpen(false);
        },
        [],
    );

    const handleNavigate = useCallback(
        (direction: -1 | 1) => {
            if (allResolvedCameras.length === 0) return;

            const currentIdx = resolvedSelected
                ? allResolvedCameras.findIndex(
                    (c) =>
                        c.shorthand === resolvedSelected.shorthand &&
                        c.pillarKey === resolvedSelected.pillarKey,
                )
                : -1;

            let nextIdx: number;
            if (currentIdx < 0) {
                nextIdx = 0;
            } else {
                nextIdx =
                    (currentIdx + direction + allResolvedCameras.length) %
                    allResolvedCameras.length;
            }

            setSelectedCamera(allResolvedCameras[nextIdx]);
        },
        [allResolvedCameras, resolvedSelected],
    );

    return (
        <div className="ps-content-wrapper">
            {/* Header Bar */}
            <header className="ps-header-bar">
                <h1 className="ps-header-title">Preview Streams</h1>
                <ServerStatusButton />
            </header>

            {/* Mobile Collapsible Camera Selection Panel */}
            <div className="ps-mobile-selector">
                <button
                    type="button"
                    className={`ps-mobile-selector-toggle ${mobileMapOpen ? "open" : ""}`}
                    onClick={() => setMobileMapOpen((prev) => !prev)}
                >
                    <div className="ps-mobile-selector-toggle-left">
                        <Map size={16} />
                        <span>
                            {selectedCamera
                                ? `Camera: ${selectedCamera.shorthand}`
                                : "Select Camera"}
                        </span>
                    </div>
                    <ChevronDown
                        size={18}
                        className={`ps-mobile-chevron ${mobileMapOpen ? "rotated" : ""}`}
                    />
                </button>

                {mobileMapOpen && (
                    <div className="ps-mobile-selector-panel">
                        {/* Server Filters inside mobile panel */}
                        <div className="ps-mobile-filters-section">
                            <ServerFilters
                                selectedServer={selectedServer}
                                onSelectServer={setSelectedServer}
                                resolvedMap={resolvedMap}
                            />
                        </div>
                        {/* Spatial Map */}
                        <div className="ps-mobile-map-section">
                            <StageSpatialMap
                                selectedCamera={selectedCamera}
                                onSelectCamera={handleMobileCameraSelect}
                                resolvedMap={resolvedMap}
                                highlightedServer={selectedServer}
                                initialViewMode="grid"
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Main Layout Grid (Desktop: 2-col / Mobile: single-col) */}
            <main className="ps-main-layout">
                {/* Left Column: Stage Spatial Map (Desktop only) */}
                <div className="ps-left-column">
                    <StageSpatialMap
                        selectedCamera={selectedCamera}
                        onSelectCamera={setSelectedCamera}
                        resolvedMap={resolvedMap}
                        highlightedServer={selectedServer}
                        initialViewMode="map"
                    />
                </div>

                {/* Right Column: Camera Preview & Server Filters */}
                <div className="ps-right-column">
                    <div className="ps-top-preview-card">
                        <CameraPreview
                            selectedCamera={resolvedSelected}
                            cameraEntry={selectedCamera}
                            allResolvedCameras={allResolvedCameras}
                            streamID={streamID}
                            onNavigate={handleNavigate}
                        />
                    </div>
                    {/* Server Filters (Desktop only) */}
                    <div className="ps-bottom-filters-card ps-desktop-only">
                        <ServerFilters
                            selectedServer={selectedServer}
                            onSelectServer={setSelectedServer}
                            resolvedMap={resolvedMap}
                        />
                    </div>
                </div>
            </main>
        </div>
    );
}

