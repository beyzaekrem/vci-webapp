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
import { ServerStatusButton, HelpButton } from "../../shared/ServerStatusModal";
import { useIntegerZoomKeyBindingsWebsocket } from "../../Videostream";
import { useSidebar } from "../../shared/Sidebar/Sidebar";
import {
    ChevronDown,
    Map,
    Menu,
    X,
} from "lucide-react";
import "./previewStreams.css";

export function PreviewStreamsPage() {
    const { openSidebar } = useSidebar();
    const clientID = useClientID();
    const cameraIndices = useCameraIndices();

    const [mobileMapExpanded, setMobileMapExpanded] = useState(false);

    // ------------------------------------------------------------------
    // Live View Logic (Spatial Map & Single Preview)
    // ------------------------------------------------------------------
    const resolvedMap = useMemo(() => buildShorthandMap(), [cameraIndices]);

    const allResolvedCameras = useMemo(() => {
        return getAllCamerasFromLayout()
            .map((e) => resolveCamera(e, resolvedMap))
            .filter((c): c is ResolvedCamera => c !== undefined);
    }, [resolvedMap]);

    const [selectedCamera, setSelectedCamera] = useState<CameraEntry | null>(null);
    const [selectedServer, setSelectedServer] = useState<number | null>(null);

    const resolvedSelected = useMemo<ResolvedCamera | null>(() => {
        if (!selectedCamera) return null;
        const match = resolvedMap.get(selectedCamera.shorthand);
        if (!match) return null;
        return { ...selectedCamera, ...match };
    }, [selectedCamera, resolvedMap]);

    const liveStreamID = useMemo(() => {
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

    // Zoom keybindings for Live View stream
    useIntegerZoomKeyBindingsWebsocket(
        liveStreamID,
        resolvedSelected?.serverIndex ?? 0
    );

    const [activeTab, setActiveTab] = useState<"map" | "stream">("map");

    return (
        <div className="ps-content-wrapper">
            {/* Header Bar */}
            <header className="ps-header-bar ps-unified-header">
                <div className="ps-header-brand">
                    <button
                        type="button"
                        className="vci-header-hamburger-btn"
                        onClick={openSidebar}
                        title="Open Navigation Menu"
                    >
                        <Menu size={18} />
                    </button>
                    <h1 className="ps-header-title">Preview</h1>
                </div>

                <div className="ps-header-right" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <HelpButton />
                    <ServerStatusButton />
                </div>
            </header>

            {/* Mobile / Responsive Segmented Tab Control */}
            <div className="ps-mobile-tab-bar-container">
                <div className="ps-mobile-tab-bar">
                    <button
                        type="button"
                        className={`ps-mobile-tab-btn ${activeTab === "map" ? "active" : ""}`}
                        onClick={() => setActiveTab("map")}
                    >
                        2D Map
                    </button>
                    <button
                        type="button"
                        className={`ps-mobile-tab-btn ${activeTab === "stream" ? "active" : ""}`}
                        onClick={() => setActiveTab("stream")}
                    >
                        Live Stream
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <main className="ps-main-layout">
                {/* 2D Spatial Map View (Desktop Left Column or Mobile Map Tab) */}
                <div className={`ps-left-column ${activeTab === "map" ? "ps-mobile-show" : "ps-mobile-hide"}`}>
                    <StageSpatialMap
                        selectedCamera={selectedCamera}
                        onSelectCamera={(cam) => {
                            setSelectedCamera(cam);
                            // Auto switch to stream view on mobile when a camera is clicked
                            if (window.innerWidth <= 768) {
                                setActiveTab("stream");
                            }
                        }}
                        resolvedMap={resolvedMap}
                        highlightedServer={selectedServer}
                        initialViewMode="grid"
                    />

                    {/* Server & Region Filters shown directly underneath Spatial Map on mobile */}
                    <div className="ps-mobile-filters-card">
                        <ServerFilters
                            selectedServer={selectedServer}
                            onSelectServer={setSelectedServer}
                            resolvedMap={resolvedMap}
                        />
                    </div>
                </div>

                {/* Right Column: Stacked Camera Preview & Desktop Filters */}
                <div className={`ps-right-column ${activeTab === "stream" ? "ps-mobile-show" : "ps-mobile-hide"}`}>
                    <div className="ps-top-preview-card">
                        <CameraPreview
                            selectedCamera={resolvedSelected}
                            streamID={liveStreamID}
                            onNavigate={handleNavigate}
                            allResolvedCameras={allResolvedCameras}
                        />
                    </div>

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
