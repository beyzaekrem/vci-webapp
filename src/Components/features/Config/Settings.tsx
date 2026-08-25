import { useEffect, useState } from "react";
import { reloadControlServer, useControlServerConfig } from "../../../network/control-server";
import { reloadCaptureServers, useServerAddresses } from "../../../network/capture-server";
import { reloadVCI, useVCIConfig } from "../../../network/vci-automation";
import { Server, Monitor, Sliders, CheckCircle2, PlayCircle, Radio } from "lucide-react";

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
    backgroundColor: "var(--vci-card-bg)",
    borderRadius: "12px",
    border: "1px solid var(--vci-card-border)",
    padding: "24px",
    boxShadow: "var(--vci-card-shadow)",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    height: "100%",
    width: "100%",
    maxWidth: "100%",
    boxSizing: "border-box",
    overflow: "hidden",
    transition: "background-color 0.25s ease, border-color 0.25s ease",
};

const titleStyle: React.CSSProperties = {
    fontSize: "16px",
    fontWeight: 700,
    color: "var(--vci-text-main)",
    margin: "0 0 4px 0",
    paddingBottom: "12px",
    borderBottom: "1px solid var(--vci-border)",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    transition: "color 0.2s ease, border-color 0.25s ease",
};

const labelStyle: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 700,
    color: "var(--vci-text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "6px",
    display: "block",
    transition: "color 0.2s ease",
};

const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    borderRadius: "8px",
    backgroundColor: "var(--vci-input-bg)",
    border: "1px solid var(--vci-input-border)",
    fontSize: "14px",
    color: "var(--vci-text-main)",
    outline: "none",
    boxSizing: "border-box",
    transition: "all 0.15s ease"
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
    const [activeMobileTab, setActiveMobileTab] = useState<"control" | "automation" | "capture">("control");

    return (
        <div className="cfg-container" style={{
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            maxWidth: "1200px",
            margin: "0 auto"
        }}>
            <EnvironmentPresetsHeader />

            {/* Mobile Segmented Tab Bar for Control / Automation / Capture */}
            <div className="cfg-mobile-tab-bar-container">
                <div className="cfg-mobile-tab-bar">
                    <button
                        type="button"
                        className={`cfg-mobile-tab-btn ${activeMobileTab === "control" ? "active" : ""}`}
                        onClick={() => setActiveMobileTab("control")}
                    >
                        Control
                    </button>
                    <button
                        type="button"
                        className={`cfg-mobile-tab-btn ${activeMobileTab === "automation" ? "active" : ""}`}
                        onClick={() => setActiveMobileTab("automation")}
                    >
                        Automation
                    </button>
                    <button
                        type="button"
                        className={`cfg-mobile-tab-btn ${activeMobileTab === "capture" ? "active" : ""}`}
                        onClick={() => setActiveMobileTab("capture")}
                    >
                        Capture
                    </button>
                </div>
            </div>

            {/* Desktop 3-Column Grid / Mobile Single Card View */}
            <div className="cfg-cards-grid">
                <div className={`cfg-card-wrapper ${activeMobileTab === "control" ? "cfg-mobile-active" : "cfg-mobile-inactive"}`}>
                    <ControlServerAddressSection />
                </div>
                <div className={`cfg-card-wrapper ${activeMobileTab === "automation" ? "cfg-mobile-active" : "cfg-mobile-inactive"}`}>
                    <VCIAutomationSection />
                </div>
                <div className={`cfg-card-wrapper ${activeMobileTab === "capture" ? "cfg-mobile-active" : "cfg-mobile-inactive"}`}>
                    <ServerAddressesSection />
                </div>
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
        <div className="cfg-presets-card">
            <div className="cfg-presets-header-text">
                <h3 className="cfg-presets-title">Quick Environment Presets</h3>
                <span className="cfg-presets-subtitle">One-click switch between environments.</span>
            </div>

            <div className="cfg-presets-buttons">
                <button
                    type="button"
                    className={`cfg-preset-btn ${isSimulatedActive ? "active" : ""}`}
                    onClick={() => applyPreset(SIMULATED_PRESET)}
                >
                    <Monitor size={15} />
                    <span>Simulated (Local)</span>
                    {isSimulatedActive && <CheckCircle2 size={14} style={{ marginLeft: "2px" }} />}
                </button>

                <button
                    type="button"
                    className={`cfg-preset-btn ${isRealRigActive ? "active" : ""}`}
                    onClick={() => applyPreset(REAL_RIG_PRESET)}
                >
                    <Server size={15} />
                    <span>Real Rig (10.3.10.x)</span>
                    {isRealRigActive && <CheckCircle2 size={14} style={{ marginLeft: "2px" }} />}
                </button>
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
            <h3 style={titleStyle}>
                <Server size={16} style={{ color: "var(--vci-primary)" }} />
                <span>Control Server Configuration</span>
            </h3>

            <div>
                <label style={labelStyle}>ADDRESS</label>
                <textarea
                    value={addressInput}
                    onChange={e => setAddressInput(e.target.value)}
                    placeholder="Enter IP address"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <button
                    type="button"
                    onClick={handleSave}
                    className="cfg-save-btn"
                >
                    Save Address
                </button>
            </div>

            <div>
                <label style={labelStyle}>PORT</label>
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
                <label style={labelStyle}>ROUTE</label>
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

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid var(--vci-border)", fontSize: 12, color: 'var(--vci-text-muted)' }}>
                Current Active: <strong style={{ color: "#22c55e", fontWeight: 700 }}>{controlServerConfig.address}</strong>
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
            <h3 style={titleStyle}>
                <Radio size={16} style={{ color: "var(--vci-primary)" }} />
                <span>Capture Servers Configuration</span>
            </h3>

            <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px", flexWrap: "wrap", gap: "6px" }}>
                    <label style={{ ...labelStyle, marginBottom: 0 }}>SERVER ADDRESSES</label>
                    <div style={{ display: "flex", gap: "4px" }}>
                        <button
                            type="button"
                            style={{ background: "none", border: "none", fontSize: "11px", padding: "0 4px", color: "var(--vci-primary)", cursor: "pointer", fontWeight: 600 }}
                            onClick={() => setServerAddressesInput(SIMULATED_PRESET.captureServers.join("\n"))}
                        >
                            + Local IPs
                        </button>
                        <span style={{ color: "var(--vci-border-light)", fontSize: "11px" }}>|</span>
                        <button
                            type="button"
                            style={{ background: "none", border: "none", fontSize: "11px", padding: "0 4px", color: "var(--vci-primary)", cursor: "pointer", fontWeight: 600 }}
                            onClick={() => setServerAddressesInput(REAL_RIG_PRESET.captureServers.join("\n"))}
                        >
                            + Rig IPs
                        </button>
                    </div>
                </div>
                <textarea
                    value={serverAddressesInput}
                    onChange={e => setServerAddressesInput(e.target.value)}
                    placeholder="One IP per line"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <button
                    type="button"
                    onClick={handleSaveServers}
                    className="cfg-save-btn"
                >
                    Save Server Addresses
                </button>
            </div>

            <div>
                <label style={labelStyle}>PORT</label>
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
                <label style={labelStyle}>ROUTE</label>
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

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid var(--vci-border)", fontSize: 12, color: 'var(--vci-text-muted)', wordBreak: "break-word" }}>
                Current Active: <strong style={{ color: "#22c55e", fontWeight: 700 }}>
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
            <h3 style={titleStyle}>
                <PlayCircle size={16} style={{ color: "var(--vci-primary)" }} />
                <span>VCI Automation Configuration</span>
            </h3>

            <div>
                <label style={labelStyle}>ADDRESS</label>
                <textarea
                    value={addressInput}
                    onChange={e => setAddressInput(e.target.value)}
                    placeholder="Enter IP address"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <button
                    type="button"
                    onClick={handleSave}
                    className="cfg-save-btn"
                >
                    Save Address
                </button>
            </div>

            <div>
                <label style={labelStyle}>PORT</label>
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
                <label style={labelStyle}>ROUTE</label>
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

            <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid var(--vci-border)", fontSize: 12, color: 'var(--vci-text-muted)' }}>
                Current Active: <strong style={{ color: "#22c55e", fontWeight: 700 }}>{vciConfig.address}</strong>
            </div>
        </div>
    );
}
