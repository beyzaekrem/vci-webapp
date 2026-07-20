import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { getVCI } from "../../network/vci-automation";
import type { LogEvent, ScriptEvent } from "../../network/vci-automation";
import { AutoScrollFollow } from "./AutoScrollFollow";

function isLogEvent(event: ScriptEvent): event is LogEvent {
    return event.type === "LOG";
}

const terminalStyle: CSSProperties = {
    margin: 0,
    padding: 12,
    minWidth: "max-content",
    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace',
    fontSize: "0.9rem",
    lineHeight: 1.5,
    color: "#212529",
};

const timestampStyle: CSSProperties = {
    color: "var(--bs-secondary)",
    fontWeight: 600,
};

const warningStyle: CSSProperties = {
    color: "var(--bs-warning)",
};

const errorStyle: CSSProperties = {
    color: "var(--bs-danger)",
};

function getSeverityStyle(logLevel: LogEvent["log_level"]): CSSProperties | undefined {
    if (logLevel === "warning") {
        return warningStyle;
    }

    if (logLevel === "error") {
        return errorStyle;
    }

    return undefined;
}

function getLogLevelLabel(logLevel: LogEvent["log_level"]) {
    return logLevel ? `${logLevel.toUpperCase()}:` : null;
}

export function ScriptLogs({ runnerId }: { runnerId: string }) {
    const [logs, setLogs] = useState<LogEvent[]>([]);

    useEffect(() => {
        const removeListener = getVCI().add_listener_output(runnerId, (msg) => {
            const fullHistory = msg.full_event_history as ScriptEvent[];
            const logs = fullHistory.filter(isLogEvent);
            setLogs(logs);
        });
        return () => {
            removeListener();
        };
    }, [runnerId]);

    return (
        <div>
            <h3>Logs</h3>
            <AutoScrollFollow
                followTrigger={logs.length}
                className="text-start"
                style={{
                    height: "300px",
                    overflow: "auto",
                    borderRadius: 8,
                    boxShadow: "inset 0 0 0 1px rgba(33, 37, 41, 0.08)",
                }}
            >
                <pre style={terminalStyle}>
                    {logs.map((log) => {
                        const severityStyle = getSeverityStyle(log.log_level);
                        const logLevelLabel = getLogLevelLabel(log.log_level);

                        return (
                            <div key={log.event_id}>
                                <span style={{ ...timestampStyle, ...severityStyle }}>
                                    [{new Date(log.timestamp * 1000).toLocaleTimeString()}]
                                </span>{" "}
                                {logLevelLabel && (
                                    <>
                                        <span style={severityStyle}>{logLevelLabel}</span>{" "}
                                    </>
                                )}
                                {log.content}
                            </div>
                        );
                    })}
                </pre>
            </AutoScrollFollow>
        </div>
    );
}
