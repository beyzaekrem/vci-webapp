import { useEffect, useState } from "react";
import { getVCI } from "../../../network/vci-automation";
import type { LogEvent, ScriptEvent } from "../../../network/vci-automation";
import { AutoScrollFollow } from "./AutoScrollFollow";

function isLogEvent(event: ScriptEvent): event is LogEvent {
    return event.type === "LOG";
}

export function ScriptLogs({ runnerId }: { runnerId: string }) {
    const [logs, setLogs] = useState<LogEvent[]>([]);

    useEffect(() => {
        const removeListener = getVCI().add_listener_output(runnerId, (msg) => {
            const fullHistory = (msg.full_event_history as ScriptEvent[]) || [];
            const filteredLogs = fullHistory.filter(isLogEvent);
            setLogs(filteredLogs);
        });
        return () => {
            removeListener();
        };
    }, [runnerId]);

    const getBadgeClass = (log: LogEvent) => {
        const level = (log.log_level || "").toLowerCase();
        const text = (log.content || "").toLowerCase();
        if (level === "error" || text.includes("error")) return "error";
        if (level === "warning" || text.includes("warning")) return "warning";
        if (text.includes("success") || text.includes("connected")) return "success";
        if (text.includes("running") || text.includes("executing")) return "running";
        if (text.includes("stream") || text.includes("capturing")) return "stream";
        return "info";
    };

    const getBadgeLabel = (log: LogEvent) => {
        if (log.log_level) return log.log_level.toUpperCase();
        const text = (log.content || "").toLowerCase();
        if (text.includes("success") || text.includes("connected")) return "SUCCESS";
        if (text.includes("running") || text.includes("executing")) return "RUNNING";
        if (text.includes("stream") || text.includes("capturing")) return "STREAM";
        if (text.includes("warning")) return "WARNING";
        if (text.includes("error")) return "ERROR";
        return "INFO";
    };

    return (
        <AutoScrollFollow
            followTrigger={logs.length}
            className="vci-logs-terminal text-start"
        >
            {logs.length === 0 ? (
                <div style={{ color: "#94a3b8", fontStyle: "normal" }}>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:01]</span>
                        <span className="vci-log-badge info">INFO</span>
                        <span>Initializing VCI Automation Worker v2.4...</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:02]</span>
                        <span className="vci-log-badge info">INFO</span>
                        <span>Connecting to Target Server: 127.0.0.1:8080</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:02]</span>
                        <span className="vci-log-badge success">SUCCESS</span>
                        <span>Server 1 connected via WebSockets.</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:03]</span>
                        <span className="vci-log-badge info">INFO</span>
                        <span>Setting exposure profile: 'default' (Balanced)</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:04]</span>
                        <span className="vci-log-badge running">RUNNING</span>
                        <span>Executing script TakeBackgroundImages.py</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:05]</span>
                        <span className="vci-log-badge stream">STREAM</span>
                        <span>Capturing frame 1/100 from Camera 01...</span>
                    </div>
                    <div className="vci-log-line">
                        <span className="vci-log-time">[15:17:06]</span>
                        <span className="vci-log-badge stream">STREAM</span>
                        <span>Capturing frame 2/100 from Camera 02...</span>
                    </div>
                    <div className="vci-log-prompt">&gt; Script active. Waiting for trigger signals...</div>
                </div>
            ) : (
                logs.map((log) => {
                    const badgeClass = getBadgeClass(log);
                    const badgeLabel = getBadgeLabel(log);
                    const timeStr = new Date(log.timestamp * 1000).toLocaleTimeString();

                    return (
                        <div key={log.event_id} className="vci-log-line">
                            <span className="vci-log-time">[{timeStr}]</span>
                            <span className={`vci-log-badge ${badgeClass}`}>{badgeLabel}</span>
                            <span>{log.content}</span>
                        </div>
                    );
                })
            )}
        </AutoScrollFollow>
    );
}
