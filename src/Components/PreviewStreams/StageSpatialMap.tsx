import { useMemo } from "react";
import {
    getAllCamerasFromLayout,
    getPillarKeys,
    getPillarNumber,
    getSlotDisplayName,
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
                    const offsetPx = (cam.slotIndex - 0.5) * 18;

                    const isActive =
                        selectedCamera?.shorthand === cam.shorthand &&
                        selectedCamera?.pillarKey === cam.pillarKey;
                    const resolved = resolvedMap.get(cam.shorthand);
                    const isResolved = !!resolved;

                    const labelNumber = cam.shorthand.replace(/^[A-Z]+/i, "").slice(-2) || "01";

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
                                left: `calc(${leftPct}% + ${offsetPx}px)`,
                                top: `${topPct}%`,
                            }}
                            title={`${cam.shorthand} – ${getSlotDisplayName(cam.slot)} (Pillar ${cam.pillarIndex})`}
                            onClick={() => {
                                if (isResolved) onSelectCamera(cam);
                            }}
                        >
                            <span>{labelNumber}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
