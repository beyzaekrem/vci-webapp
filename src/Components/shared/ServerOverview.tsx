import { Accordion } from "react-bootstrap";
import { getServers } from "../../network/capture-server";
import { useSerialNumber, useCameraCount } from "../../network/capture-server";
import { ServerStatusInfo as WebsocketStatusInfo } from "../../network/interceptor";
import { InfoPopUpBadge } from "../../Utility/UI";
import { NavLink } from "react-router-dom";
import { useToggleTriggerBox } from "../features/CameraHooks";
import "./ServerOverview.css";

export function ServerOverview() {

    useToggleTriggerBox();

    const serverCount = getServers().servers.length;

    return (
        <div className="server-overview-container">
            <div className="server-overview-header">
                <div className="server-overview-header-text">
                    <h3 className="server-overview-title">Capture Servers Overview</h3>
                    <p className="server-overview-subtitle">
                        {serverCount} {serverCount === 1 ? "server" : "servers"} configured • Active
                    </p>
                </div>
            </div>

            <Accordion defaultActiveKey="0" className="vci-server-overview-accordion">
                {getServers().map((_, serverIndex) => {
                    return (
                        <ServerOverviewItem serverIndex={serverIndex} key={serverIndex} />
                    );
                })}
            </Accordion>

            <div className="vci-add-server-container">
                <NavLink to="/config" className="vci-add-server-btn">
                    + Add Capture Server
                </NavLink>
            </div>
        </div>
    );
}

function SerialNumberInfo({ camIndex, serverIndex }: { camIndex: number; serverIndex: number }) {
    const sn = useSerialNumber(serverIndex, camIndex);
    const displaySN = sn ? sn : "unknown";
    const content =
        "The Serial Number of camera " +
        camIndex +
        " on server " +
        serverIndex +
        " is " +
        sn +
        (!sn ? ". Maybe you need to set its handle or refresh the page." : "");
    return (
        <InfoPopUpBadge
            bg={sn && sn != "unknown" ? "success" : "warning"}
            placement="right"
            icon=""
            title={displaySN}
            content={content}
            longTitle={"Serial Number is " + displaySN}
        />
    );
}


function ServerOverviewItem({ serverIndex }: { serverIndex: number }) {
    const server = getServers().getServer(serverIndex);
    const count = useCameraCount(serverIndex);
    const domain = server ? server.getDomain() : `Server ${serverIndex + 1}`;

    return (
        <Accordion.Item eventKey={serverIndex + ""} key={serverIndex}>
            <Accordion.Header>
                <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", width: "100%" }}>
                    <span style={{ fontFamily: "SF Mono, Monaco, monospace", fontWeight: 700, color: "var(--vci-text-main)" }}>{domain}</span>
                    {server && <ServerStatusInfo serverIndex={serverIndex} />}
                    <span style={{ fontSize: "0.85rem", color: "var(--vci-text-muted)", fontWeight: 500 }}>({count} {count === 1 ? "camera" : "cameras"})</span>
                </span>
            </Accordion.Header>
            <Accordion.Body>
                {count === 0 ? (
                    <div style={{ fontSize: "0.85rem", color: "var(--vci-text-dim)", textAlign: "center", padding: "8px 0" }}>
                        No active cameras detected on this node.
                    </div>
                ) : (
                    <div className="vci-camera-badge-grid">
                        {Array(count)
                            .fill("aa")
                            .map((_, i) => {
                                return (
                                    <div key={i} className="vci-camera-badge-card">
                                        <span style={{ fontWeight: 600 }}>Camera {i + 1}</span>
                                        <SerialNumberInfo serverIndex={serverIndex} camIndex={i} />
                                    </div>
                                );
                            })}
                    </div>
                )}
            </Accordion.Body>
        </Accordion.Item>
    );
}

function ServerStatusInfo({ serverIndex }: { serverIndex: number }) {
    const server = getServers().getServer(serverIndex);
    if (!server) return null;

    return (
        <WebsocketStatusInfo
            socket={server.socket}
        />
    );
}
