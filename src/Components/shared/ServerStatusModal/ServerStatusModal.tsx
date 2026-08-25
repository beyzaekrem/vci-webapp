/**
 * Server Status Modal - displays real-time connection status of all servers.
 * Shows Control Server, VCI Automation, and all Capture Servers with live WebSocket status.
 * @packageDocumentation
 */
import { useState } from "react";
import { Button, Modal, Badge, Spinner } from "react-bootstrap";
import { getServers } from "../../../network/capture-server";
import { useConnectionStatus, ReadyState } from "../../../network/interceptor";
import { getControlServer } from "../../../network/control-server";
import { getVCI } from "../../../network/vci-automation";
import "./ServerStatusModal.css";


/* ─── Status label config ─── */
const STATUS_CONFIG = {
    [ReadyState.OPEN]:            { label: "Online",       bg: "success"   as const, dotClass: "dot-online"      },
    [ReadyState.CONNECTING]:      { label: "Connecting",   bg: "warning"   as const, dotClass: "dot-connecting"  },
    [ReadyState.CLOSING]:         { label: "Closing",      bg: "secondary" as const, dotClass: "dot-closing"     },
    [ReadyState.CLOSED]:          { label: "Offline",      bg: "danger"    as const, dotClass: "dot-offline"     },
    [ReadyState.UNINSTANTIATED]:  { label: "Not Started",  bg: "secondary" as const, dotClass: "dot-inactive"   },
};

function getStatusInfo(state: number) {
    return STATUS_CONFIG[state as ReadyState] || STATUS_CONFIG[ReadyState.CLOSED];
}


/* ─── Reusable status row ─── */
function StatusRow({ address, state }: { address: string; state: number }) {
    const info = getStatusInfo(state);

    return (
        <div className="server-status-row">
            <div className="server-status-info">
                <span className={`server-status-dot ${info.dotClass}`} />
                <span className="server-status-address">{address}</span>
            </div>
            <Badge pill bg={info.bg} className="server-status-badge">
                {state === ReadyState.CONNECTING ? (
                    <>
                        <Spinner animation="border" size="sm" style={{ width: 10, height: 10, marginRight: 4 }} />
                        {info.label}
                    </>
                ) : (
                    info.label
                )}
            </Badge>
        </div>
    );
}

/* ─── Capture Server row ─── */
function CaptureServerStatusRow({ serverIndex }: { serverIndex: number }) {
    const server = getServers().getServer(serverIndex);
    if (!server) return null;
    const state = useConnectionStatus(server.socket);
    return <StatusRow address={server.getDomain()} state={state} />;
}

/* ─── Control Server row (safe for missing singleton) ─── */
function ControlServerStatusRowInner() {
    const cs = getControlServer();
    const state = useConnectionStatus(cs.socket);
    let address: string;
    try {
        const url = new URL(cs.url);
        address = url.hostname;
    } catch {
        address = "—";
    }
    return <StatusRow address={address} state={state} />;
}

function ControlServerStatusRow() {
    try {
        getControlServer();
        return <ControlServerStatusRowInner />;
    } catch {
        return <StatusRow address="—" state={ReadyState.UNINSTANTIATED} />;
    }
}

/* ─── VCI Automation row (safe for missing singleton) ─── */
function VCIServerStatusRowInner() {
    const vci = getVCI();
    const state = useConnectionStatus(vci.socket);
    return <StatusRow address="VCI Automation" state={state} />;
}

function VCIServerStatusRow() {
    try {
        getVCI();
        return <VCIServerStatusRowInner />;
    } catch {
        return <StatusRow address="VCI Automation" state={ReadyState.UNINSTANTIATED} />;
    }
}


/* ─── Modal ─── */

/**
 * Modal popup showing the real-time connection status of all servers.
 * Can be used from any page by controlling the `show` / `onHide` props.
 */
export function ServerStatusModal({ show, onHide }: { show: boolean; onHide: () => void }) {
    const servers = getServers();
    const serverCount = servers.servers.length;

    return (
        <Modal show={show} onHide={onHide} centered className="server-status-modal">
            <Modal.Header closeButton className="server-status-modal-header">
                <Modal.Title className="server-status-modal-title">
                    Server Connection Status
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="server-status-modal-body">
                {/* Control Server */}
                <div className="server-status-section">
                    <h6 className="server-status-section-title">Control Server</h6>
                    <ControlServerStatusRow />
                </div>

                {/* VCI Automation */}
                <div className="server-status-section">
                    <h6 className="server-status-section-title">VCI Automation</h6>
                    <VCIServerStatusRow />
                </div>

                {/* Capture Servers */}
                <div className="server-status-section">
                    <h6 className="server-status-section-title">
                        Capture Servers
                        <Badge bg="secondary" pill style={{ marginLeft: 8, fontSize: "0.7rem" }}>
                            {serverCount}
                        </Badge>
                    </h6>
                    {serverCount === 0 ? (
                        <p className="server-status-empty">No capture servers configured.</p>
                    ) : (
                        servers.map((_, i) => (
                            <CaptureServerStatusRow key={i} serverIndex={i} />
                        ))
                    )}
                </div>

                <div className="server-status-footer-note">
                    Status is updated in real-time via WebSocket connection state.
                </div>
            </Modal.Body>
        </Modal>
    );
}


/* ─── Convenience button + modal combo ─── */

/**
 * Self-contained button that opens the server status modal.
 * Drop this component anywhere to add a "Show Connection Status" button.
 */
export function ServerStatusButton({ className, style }: { className?: string; style?: React.CSSProperties }) {
    const [show, setShow] = useState(false);
    return (
        <>
            <Button
                variant="outline-secondary"
                size="sm"
                onClick={() => setShow(true)}
                className={`server-status-trigger-btn ${className || ""}`}
                style={style}
            >
                <span className="server-status-trigger-dot" />
                <span className="server-btn-text-full">Connection Status</span>
                <span className="server-btn-text-short">Status</span>
            </Button>
            <ServerStatusModal show={show} onHide={() => setShow(false)} />
        </>
    );
}

/**
 * Self-contained Help & Shortcut button styled matching connection status pill.
 */
export function HelpButton({ className, style }: { className?: string; style?: React.CSSProperties }) {
    const handleHelpClick = () => {
        const event = new KeyboardEvent("keydown", { key: "h", bubbles: true });
        window.dispatchEvent(event);
    };

    return (
        <Button
            variant="outline-secondary"
            size="sm"
            onClick={handleHelpClick}
            className={`server-status-trigger-btn help-trigger-btn ${className || ""}`}
            style={style}
            title="Open Help & Shortcuts (Press h)"
        >
            <span className="help-btn-text-full">Help &amp; Shortcuts (h)</span>
            <span className="help-btn-text-short">Help (h)</span>
        </Button>
    );
}
