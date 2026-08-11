import { useEffect, useState } from "react";
import { Button } from "react-bootstrap";
import { reloadControlServer, useControlServerConfig } from "../../../network/control-server";
import { reloadCaptureServers, useServerAddresses } from "../../../network/capture-server";
import { reloadVCI, useVCIConfig } from "../../../network/vci-automation";
import { Server, Monitor, Zap, CheckCircle2 } from "lucide-react";

export const SIMULATED_PRESET = {
    name: "Simulated Mode (Local)",
    controlServer: "127.0.0.1",
    vciAutomation: "127.0.0.1",
    captureServers: ["127.0.0.1"],
};

export const REAL_RIG_PRESET = {
    name: "Real Production Rig",
    controlServer: "10.3.10.20",
    vciAutomation: "10.3.10.20",
    captureServers: [
        "10.3.10.1",
        "10.3.10.2",
        "10.3.10.3",
        "10.3.10.4",
        "10.3.10.5",
        "10.3.10.6",
        "10.3.10.7",
        "10.3.10.8",
        "10.3.10.9",
        "10.3.10.10",
        "10.3.10.11",
        "10.3.10.12",
        "10.3.10.13",
        "10.3.10.14",
        "10.3.10.15",
    ],
};

const cardStyle: React.CSSProperties = {
    backgroundColor: "#ffffff",
    borderRadius: "12px",
    border: "1px solid #cbd5e1",
    padding: "24px",
    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    height: "100%",
};

const titleStyle: React.CSSProperties = {
    fontSize: "16px",
    fontWeight: 700,
    color: "#0f172a",
    margin: "0 0 4px 0",
    paddingBottom: "12px",
    borderBottom: "1px solid #f1f5f9"
};

const labelStyle: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 700,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "6px",
    display: "block"
};

const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#1e293b",
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.15s ease"
};

const monoInputStyle: React.CSSProperties = {
    ...inputStyle,
    fontFamily: "SF Mono, Monaco, Inconsolata, Fira Code, monospace",
    fontSize: "13px"
};

/**
 * Main settings component for configuring control server, capture server addresses, and favourite parameters.
 */
export default function Settings() {
    return (
        <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "24px",
            maxWidth: "1200px",
            margin: "0 auto"
        }}>
            <EnvironmentPresetsHeader />
            <div className="cfg-cards-grid" style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "24px",
                alignItems: "stretch",
            }}>
                <ControlServerAddressSection />
                <VCIAutomationSection />
                <ServerAddressesSection />
            </div>
        </div>
    );
}

function EnvironmentPresetsHeader() {
    const [captureConfig, setCaptureConfig] = useServerAddresses();
    const [controlConfig, setControlConfig] = useControlServerConfig();
    const [vciConfig, setVciConfig] = useVCIConfig();

    const isSimulatedActive =
        captureConfig.addresses.length === 1 &&
        captureConfig.addresses[0] === "127.0.0.1" &&
        controlConfig.address === "127.0.0.1";

    const isRealRigActive =
        captureConfig.addresses.length === REAL_RIG_PRESET.captureServers.length &&
        captureConfig.addresses[0] === "10.3.10.1" &&
        controlConfig.address === "10.3.10.20";

    const applyPreset = (preset: typeof SIMULATED_PRESET | typeof REAL_RIG_PRESET) => {
        setControlConfig({ ...controlConfig, address: preset.controlServer });
        setVciConfig({ ...vciConfig, address: preset.vciAutomation });
        setCaptureConfig({ ...captureConfig, addresses: preset.captureServers });
        window.location.reload();
    };

    return (
        <div className="cfg-presets-card" style={{
            backgroundColor: "#ffffff",
            borderRadius: "12px",
            border: "1px solid #cbd5e1",
            borderLeft: "5px solid #00223d",
            padding: "20px 24px",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "16px",
        }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Zap size={18} style={{ color: "#0284c7" }} />
                    <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#0f172a", margin: 0 }}>
                        Quick Environment Presets
                    </h3>
                </div>
                <span style={{ fontSize: "13px", color: "#64748b" }}>
                    One-click switch between Simulated Mode (Local) and Real Production Rig (10.3.10.x).
                </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <Button
                    variant={isSimulatedActive ? "primary" : "outline-primary"}
                    size="sm"
                    onClick={() => applyPreset(SIMULATED_PRESET)}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        fontWeight: 600,
                        padding: "8px 14px",
                        backgroundColor: isSimulatedActive ? "#00223d" : "transparent",
                        borderColor: "#00223d",
                        color: isSimulatedActive ? "#ffffff" : "#00223d",
                    }}
                >
                    <Monitor size={15} />
                    <span>Simulated Mode (Local 127.0.0.1)</span>
                    {isSimulatedActive && <CheckCircle2 size={14} style={{ marginLeft: "2px" }} />}
                </Button>

                <Button
                    variant={isRealRigActive ? "primary" : "outline-primary"}
                    size="sm"
                    onClick={() => applyPreset(REAL_RIG_PRESET)}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        fontWeight: 600,
                        padding: "8px 14px",
                        backgroundColor: isRealRigActive ? "#00223d" : "transparent",
                        borderColor: "#00223d",
                        color: isRealRigActive ? "#ffffff" : "#00223d",
                    }}
                >
                    <Server size={15} />
                    <span>Real Production Rig (10.3.10.x)</span>
                    {isRealRigActive && <CheckCircle2 size={14} style={{ marginLeft: "2px" }} />}
                </Button>
            </div>
        </div>
    );
}

/**
 * Section for viewing and updating the control server address.
 */
function ControlServerAddressSection() {
    const [controlServerConfig, setControlServerConfig] = useControlServerConfig();
    const [addressInput, setAddressInput] = useState(controlServerConfig.address);

    useEffect(() => {
        setAddressInput(controlServerConfig.address);
    }, [controlServerConfig]);

    const handleSave = () => {
        setControlServerConfig({
            ...controlServerConfig,
            address: addressInput,
        });
        window.location.reload();
    };

    return (
        <div style={cardStyle}>
            <h3 style={titleStyle}>Control Server</h3>

            <div>
                <label style={labelStyle}>Address</label>
                <textarea
                    value={addressInput}
                    onChange={e => setAddressInput(e.target.value)}
                    placeholder="Enter IP address"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <Button variant="primary" size="sm" onClick={handleSave} style={{ width: "100%", marginTop: 8, backgroundColor: "#0284c7", borderColor: "#0284c7" }}>
                    Save Address
                </Button>
            </div>

            <div>
                <label style={labelStyle}>Port</label>
                <input
                    type="text"
                    value={controlServerConfig.port || ""}
                    onChange={e => {
                        setControlServerConfig({ ...controlServerConfig, port: parseInt(e.target.value) || undefined });
                        reloadControlServer();
                    }}
                    placeholder="Default 2443"
                    style={monoInputStyle}
                />
            </div>

            <div>
                <label style={labelStyle}>Route</label>
                <input
                    type="text"
                    value={controlServerConfig.route || ""}
                    onChange={e => {
                        setControlServerConfig({ ...controlServerConfig, route: e.target.value || undefined });
                        reloadControlServer();
                    }}
                    placeholder="Default /websocket"
                    style={monoInputStyle}
                />
            </div>

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid #f1f5f9", fontSize: 12, color: '#64748b' }}>
                Current Active: <b style={{ color: "#0f172a" }}>{controlServerConfig.address}</b>
            </div>
        </div>
    );
}

/**
 * Section for viewing and updating the list of capture server addresses.
 */
function ServerAddressesSection() {
    const [captureServerConfig, setCaptureServerConfig] = useServerAddresses();

    const serverAddresses = captureServerConfig.addresses;
    const [serverAddressesInput, setServerAddressesInput] = useState(serverAddresses.join("\n"));

    useEffect(() => {
        setServerAddressesInput(serverAddresses.join("\n"));
    }, [serverAddresses]);

    const handleSaveServers = () => {
        const addresses = serverAddressesInput
            .split(/\r?\n/)
            .map(addr => addr.trim())
            .filter(addr => addr.length > 0);
        setCaptureServerConfig({ ...captureServerConfig, addresses });
        window.location.reload();
    };

    return (
        <div style={cardStyle}>
            <h3 style={titleStyle}>Capture Servers</h3>

            <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                    <label style={{ ...labelStyle, marginBottom: 0 }}>Server Addresses</label>
                    <div style={{ display: "flex", gap: "4px" }}>
                        <Button
                            variant="link"
                            size="sm"
                            style={{ fontSize: "11px", padding: "0 4px", color: "#0284c7", textDecoration: "none", fontWeight: 600 }}
                            onClick={() => setServerAddressesInput(SIMULATED_PRESET.captureServers.join("\n"))}
                        >
                            + Local IPs
                        </Button>
                        <span style={{ color: "#cbd5e1", fontSize: "11px" }}>|</span>
                        <Button
                            variant="link"
                            size="sm"
                            style={{ fontSize: "11px", padding: "0 4px", color: "#0284c7", textDecoration: "none", fontWeight: 600 }}
                            onClick={() => setServerAddressesInput(REAL_RIG_PRESET.captureServers.join("\n"))}
                        >
                            + Rig IPs
                        </Button>
                    </div>
                </div>
                <textarea
                    value={serverAddressesInput}
                    onChange={e => setServerAddressesInput(e.target.value)}
                    placeholder="One IP per line"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <Button variant="primary" size="sm" onClick={handleSaveServers} style={{ width: "100%", marginTop: 8, backgroundColor: "#0284c7", borderColor: "#0284c7" }}>
                    Save Server Addresses
                </Button>
            </div>

            <div>
                <label style={labelStyle}>Port</label>
                <input
                    type="text"
                    value={captureServerConfig.port || ""}
                    onChange={e => {
                        setCaptureServerConfig({ ...captureServerConfig, port: parseInt(e.target.value) || undefined });
                        reloadCaptureServers();
                    }}
                    placeholder="Default 2443"
                    style={monoInputStyle}
                />
            </div>

            <div>
                <label style={labelStyle}>Route</label>
                <input
                    type="text"
                    value={captureServerConfig.route || ""}
                    onChange={e => {
                        setCaptureServerConfig({ ...captureServerConfig, route: e.target.value || undefined });
                        reloadCaptureServers();
                    }}
                    placeholder="Default /websocket"
                    style={monoInputStyle}
                />
            </div>

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid #f1f5f9", fontSize: 12, color: '#64748b' }}>
                Current Active: <strong style={{ color: "#0f172a" }}>
                    {serverAddresses.length === 0
                        ? "None"
                        : serverAddresses.length <= 2
                        ? serverAddresses.join(", ")
                        : `${serverAddresses.length} Active Nodes (${serverAddresses[0]} ... ${serverAddresses[serverAddresses.length - 1]})`}
                </strong>
            </div>
        </div>
    );
}

function VCIAutomationSection() {
    const [vciConfig, setVciConfig] = useVCIConfig();
    const [addressInput, setAddressInput] = useState(vciConfig.address);

    useEffect(() => {
        setAddressInput(vciConfig.address);
    }, [vciConfig]);

    const handleSave = () => {
        setVciConfig({
            ...vciConfig,
            address: addressInput,
        });
        window.location.reload();
    };

    return (
        <div style={cardStyle}>
            <h3 style={titleStyle}>VCI Automation</h3>

            <div>
                <label style={labelStyle}>Address</label>
                <textarea
                    value={addressInput}
                    onChange={e => setAddressInput(e.target.value)}
                    placeholder="Enter IP address"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <Button variant="primary" size="sm" onClick={handleSave} style={{ width: "100%", marginTop: 8, backgroundColor: "#0284c7", borderColor: "#0284c7" }}>
                    Save Address
                </Button>
            </div>

            <div>
                <label style={labelStyle}>Port</label>
                <input
                    type="text"
                    value={vciConfig.port || ""}
                    onChange={e => {
                        setVciConfig({ ...vciConfig, port: parseInt(e.target.value) || undefined });
                        reloadVCI();
                    }}
                    placeholder="Default 2525"
                    style={monoInputStyle}
                />
            </div>

            <div>
                <label style={labelStyle}>Route</label>
                <input
                    type="text"
                    value={vciConfig.route || ""}
                    onChange={e => {
                        setVciConfig({ ...vciConfig, route: e.target.value || undefined });
                        reloadVCI();
                    }}
                    placeholder="Route"
                    style={monoInputStyle}
                />
            </div>

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid #f1f5f9", fontSize: 12, color: '#64748b' }}>
                Current Active: <b style={{ color: "#0f172a" }}>{vciConfig.address}</b>
            </div>
        </div>
    );
}
