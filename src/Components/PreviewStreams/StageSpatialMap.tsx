import { useMemo } from "react";
import {
    getAllCamerasFromLayout,
    getPillarKeys,
    getPillarNumber,
    getSlotDisplayName,
    systemLayout,
    type CameraEntry,
    type SlotName,
} from "./systemLayoutData";

const SLOT_Y: Record<SlotName, number> = {
    ceiling: 0.12,
    rig_upper: 0.32,
    center: 0.52,
    rig_low: 0.72,
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
}

export function StageSpatialMap({
    selectedCamera,
    onSelectCamera,
    resolvedMap,
    highlightedServer,
}: StageSpatialMapProps) {
    const pillarKeys = useMemo(() => getPillarKeys(), []);
    const allCameras = useMemo(() => getAllCamerasFromLayout(), []);

    const visibleCameras = useMemo(() => {
        if (highlightedServer === null) return allCameras;
        return allCameras.filter((cam) => {
            const resolved = resolvedMap.get(cam.shorthand);
            return resolved && resolved.serverIndex === highlightedServer;
        });
    }, [allCameras, highlightedServer, resolvedMap]);

    const totalPillars = pillarKeys.length;

    return (
        <div className="ps-card ps-map-card">
            <h3 className="ps-card-title">Stage Spatial Map</h3>
            <p className="ps-card-subtitle">Interactive Camera Layout</p>

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

                {/* Camera Circular Nodes */}
                {visibleCameras.map((cam) => {
                    const pillarIdx = pillarKeys.indexOf(cam.pillarKey);
                    if (pillarIdx < 0) return null;

                    const leftPct = ((pillarIdx + 0.5) / totalPillars) * 100;
                    const topPct = SLOT_Y[cam.slot] * 100;

                    // Stagger horizontal & vertical offsets so overlapping dots on the same slot don't obscure each other
                    const totalInSlot = (systemLayout.positions[cam.pillarKey]?.[cam.slot] || []).length;
                    const offsetX = (cam.slotIndex - (totalInSlot - 1) / 2) * 22;
                    const offsetY = totalInSlot > 1 ? (cam.slotIndex % 2 === 1 ? -12 : 12) : 0;

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
    );
}
