import { useMemo } from "react";
import { getServers } from "../../../network/capture-server";
import { getAllCamerasFromLayout } from "./systemLayoutData";

interface ServerFiltersProps {
    selectedServer: number | null;
    onSelectServer: (serverIndex: number | null) => void;
    resolvedMap: Map<string, { serverIndex: number; cameraIndex: number }>;
}

export function ServerFilters({
    selectedServer,
    onSelectServer,
    resolvedMap,
}: ServerFiltersProps) {
    const servers = getServers();
    const allCameras = useMemo(() => getAllCamerasFromLayout(), []);

    const serverCounts = useMemo(() => {
        const counts = new Map<number, number>();
        for (const cam of allCameras) {
            const resolved = resolvedMap.get(cam.shorthand);
            if (resolved) {
                counts.set(resolved.serverIndex, (counts.get(resolved.serverIndex) || 0) + 1);
            }
        }
        return counts;
    }, [allCameras, resolvedMap]);

    const totalResolved = Array.from(serverCounts.values()).reduce((a, b) => a + b, 0);

    return (
        <div className="ps-card ps-filters-card">
            <div className="ps-filters-header">
                <div>
                    <h3 className="ps-card-title">Server &amp; Region Filters</h3>
                    <p className="ps-card-subtitle">Select server to highlight cameras on spatial map</p>
                </div>
            </div>

            {/* Compact Horizontal Chip Box Grid */}
            <div className="ps-server-chips-container">
                {/* Far Left: All Servers Chip */}
                <button
                    type="button"
                    className={`ps-server-chip ${selectedServer === null ? "active" : ""}`}
                    onClick={() => onSelectServer(null)}
                >
                    <span className="ps-chip-title">All Servers</span>
                    <span className="ps-chip-badge">{totalResolved} Cams</span>
                </button>

                {/* Server Chips 1, 2, 3... N */}
                {servers.servers.map((server, idx) => {
                    const count = serverCounts.get(idx) || 0;
                    return (
                        <button
                            key={idx}
                            type="button"
                            className={`ps-server-chip ${selectedServer === idx ? "active" : ""}`}
                            onClick={() => onSelectServer(idx)}
                            title={`Server ${idx + 1} (${server.getDomain()}) - ${count} cameras`}
                        >
                            <span className="ps-chip-title">S{idx + 1}</span>
                            <span className="ps-chip-badge">{count}</span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
