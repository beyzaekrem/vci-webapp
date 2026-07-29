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
import { useClientID } from "../../Utility/Storage";
import { getServers, useCameraIndices } from "../../network/capture-server";
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
        server.switchMode("livestream");
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

    return (
        <div className="ps-content-wrapper">
            {/* Header Bar */}
            <header className="ps-header-bar">
                <h1 className="ps-header-title">Preview Streams</h1>
            </header>

            {/* Main Layout Grid */}
            <main className="ps-main-layout">
                {/* Left Column: Stage Spatial Map (Tall Card) */}
                <div className="ps-left-column">
                    <StageSpatialMap
                        selectedCamera={selectedCamera}
                        onSelectCamera={setSelectedCamera}
                        resolvedMap={resolvedMap}
                        highlightedServer={selectedServer}
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
                    <div className="ps-bottom-filters-card">
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
