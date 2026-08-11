import { useState, useMemo } from "react";
import {
    getAllCamerasFromLayout,
    getPillarKeys,
    getPillarNumber,
    getSlotDisplayName,
    systemLayout,
    type CameraEntry,
    type SlotName,
} from "./systemLayoutData";
import { LayoutGrid, Map as MapIcon } from "lucide-react";

const SLOT_Y: Record<SlotName, number> = {
    ceiling: 0.10,
    rig_upper: 0.30,
    center: 0.50,
    rig_low: 0.70,
    floor: 0.90,
};

function formatCameraNodeLabel(shorthand: string): string {
    return shorthand;
}

interface StageSpatialMapProps {
    selectedCamera: CameraEntry | null;
    onSelectCamera: (camera: CameraEntry) => void;
    resolvedMap: Map<string, { serverIndex: number; cameraIndex: number }>;
    highlightedServer: number | null;
    initialViewMode?: "map" | "grid";
}

export function StageSpatialMap({
    selectedCamera,
    onSelectCamera,
    resolvedMap,
    highlightedServer,
    initialViewMode = "grid",
}: StageSpatialMapProps) {
    const [viewMode, setViewMode] = useState<"map" | "grid">(initialViewMode);

    const pillarKeys = useMemo(() => getPillarKeys(), []);
    const allCameras = useMemo(() => getAllCamerasFromLayout(), []);

    const visibleCameras = useMemo(() => {
        if (highlightedServer === null) return allCameras;
        return allCameras.filter((cam) => {
            const resolved = resolvedMap.get(cam.shorthand);
            return resolved && resolved.serverIndex === highlightedServer;
        });
    }, [allCameras, highlightedServer, resolvedMap]);

    // Group cameras by pillar for Grid Mode
    const camerasByPillar = useMemo(() => {
        const map = new Map<string, CameraEntry[]>();
        for (const pKey of pillarKeys) {
            map.set(pKey, []);
        }
        for (const cam of visibleCameras) {
            const list = map.get(cam.pillarKey);
            if (list) list.push(cam);
        }
        return map;
    }, [pillarKeys, visibleCameras]);

    const totalPillars = pillarKeys.length;

    return (
        <div className="ps-card ps-map-card">
            {/* Card Header with View Mode Switcher */}
            <div className="ps-map-header">
                <div>
                    <h3 className="ps-card-title">Stage Spatial Map</h3>
                    <p className="ps-card-subtitle">Interactive Camera Layout</p>
                </div>

                <div className="ps-view-toggle-group">
                    <button
                        type="button"
                        className={`ps-view-toggle-btn ${viewMode === "grid" ? "active" : ""}`}
                        onClick={() => setViewMode("grid")}
                        title="Touch Grid View (Grouped by Pillar)"
                    >
                        <LayoutGrid size={14} />
                        <span>Grid</span>
                    </button>
                    <button
                        type="button"
                        className={`ps-view-toggle-btn ${viewMode === "map" ? "active" : ""}`}
                        onClick={() => setViewMode("map")}
                        title="2D Spatial Map View"
                    >
                        <MapIcon size={14} />
                        <span>Map</span>
                    </button>
                </div>
            </div>

            {/* View Mode 1: Touchable Pillar Grid */}
            {viewMode === "grid" ? (
                <div className="ps-pillar-grid-container">
                    {pillarKeys.map((pKey) => {
                        const pNum = getPillarNumber(pKey);
                        const cams = camerasByPillar.get(pKey) || [];
                        if (cams.length === 0) return null;

                        return (
                            <div key={pKey} className="ps-pillar-group">
                                <div className="ps-pillar-group-header">
                                    <span className="ps-pillar-badge">Pillar {pNum}</span>
                                    <span className="ps-pillar-count">{cams.length} Cams</span>
                                </div>
                                <div className="ps-pillar-chips">
                                    {cams.map((cam) => {
                                        const isActive =
                                            selectedCamera?.shorthand === cam.shorthand &&
                                            selectedCamera?.pillarKey === cam.pillarKey;
                                        const resolved = resolvedMap.get(cam.shorthand);
                                        const isResolved = !!resolved;

                                        return (
                                            <button
                                                key={`${cam.pillarKey}-${cam.slot}-${cam.slotIndex}`}
                                                type="button"
                                                className={`ps-grid-cam-chip ${isActive ? "active" : ""} ${!isResolved ? "unresolved" : ""}`}
                                                disabled={!isResolved}
                                                onClick={() => {
                                                    if (isResolved) onSelectCamera(cam);
                                                }}
                                                title={`${cam.shorthand} – ${getSlotDisplayName(cam.slot)} (Pillar ${cam.pillarIndex})${resolved ? ` [Server ${resolved.serverIndex + 1}]` : " [Offline]"}`}
                                            >
                                                <span className="ps-chip-cam-name">{cam.shorthand}</span>
                                                <span className="ps-chip-slot-name">{cam.slot.replace("rig_", "").substring(0, 3)}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                /* View Mode 2: 2D Spatial Map Diagram (Scrollable / Pannable) */
                <div className="ps-map-scroll-wrapper">
                    <div className="ps-map-grid">
                        {/* Pillar Vertical Dashed Lines */}
                        {pillarKeys.map((key, i) => {
                            const pNum = getPillarNumber(key);
                            const leftPct = ((i + 0.5) / totalPillars) * 100;
                            return (
                                <div key={key} className="ps-pillar-col" style={{ left: `${leftPct}%` }}>
                                    <span className="ps-pillar-label">P{pNum}</span>
                                    <div className="ps-pillar-line" />
                                </div>
                            );
                        })}

                        {/* Camera Circular Nodes with Non-Overlapping Spacing */}
                        {visibleCameras.map((cam) => {
                            const pillarIdx = pillarKeys.indexOf(cam.pillarKey);
                            if (pillarIdx < 0) return null;

                            const leftPct = ((pillarIdx + 0.5) / totalPillars) * 100;
                            const topPct = SLOT_Y[cam.slot] * 100;

                            // Precise non-overlapping horizontal & vertical offsets
                            const totalInSlot = (systemLayout.positions[cam.pillarKey]?.[cam.slot] || []).length;
                            const offsetX = (cam.slotIndex - (totalInSlot - 1) / 2) * 44;
                            const offsetY = totalInSlot > 1 ? (cam.slotIndex % 2 === 1 ? -14 : 14) : 0;

                            const isActive =
                                selectedCamera?.shorthand === cam.shorthand &&
                                selectedCamera?.pillarKey === cam.pillarKey;
                            const resolved = resolvedMap.get(cam.shorthand);
                            const isResolved = !!resolved;

                            const nodeLabel = formatCameraNodeLabel(cam.shorthand);

                            const classes = [
                                "ps-cam-node",
                                isActive && "active",
                                !isResolved && "unresolved",
                            ].filter(Boolean).join(" ");

                            return (
                                <div
                                    key={`${cam.pillarKey}-${cam.slot}-${cam.slotIndex}`}
                                    className={classes}
                                    style={{
                                        left: `calc(${leftPct}% + ${offsetX}px)`,
                                        top: `calc(${topPct}% + ${offsetY}px)`,
                                    }}
                                    title={`${cam.shorthand} – ${getSlotDisplayName(cam.slot)} (Pillar ${cam.pillarIndex})`}
                                    onClick={() => {
                                        if (isResolved) onSelectCamera(cam);
                                    }}
                                >
                                    <span>{nodeLabel}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
