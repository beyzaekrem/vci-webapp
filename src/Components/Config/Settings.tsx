import { useEffect, useState } from "react";
import { Button } from "react-bootstrap";
import { reloadControlServer, useControlServerConfig } from "../../network/control-server";
import { reloadCaptureServers, useServerAddresses } from "../../network/capture-server";
import { reloadVCI, useVCIConfig } from "../../network/vci-automation";

/**
 * Main settings component for configuring control server, capture server addresses, and favourite parameters.
 */
export default function Settings() {
    return (
        <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "24px",
            maxWidth: "1200px",
            margin: "0 auto"
        }}>
            <ControlServerAddressSection />
            <VCIAutomationSection />
            <ServerAddressesSection />
        </div>
    );
}

const cardStyle: React.CSSProperties = {
    backgroundColor: "#ffffff",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    padding: "24px",
    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
    display: "flex",
    flexDirection: "column",
    gap: "16px"
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
    fontSize: "12px",
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
                <Button variant="primary" size="sm" onClick={handleSave} style={{ width: "100%", marginTop: 8 }}>
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
                <label style={labelStyle}>Server Addresses (One per line)</label>
                <textarea
                    value={serverAddressesInput}
                    onChange={e => setServerAddressesInput(e.target.value)}
                    placeholder="One IP per line"
                    rows={4}
                    style={{ ...monoInputStyle, height: "92px", resize: "none" }}
                />
                <Button variant="primary" size="sm" onClick={handleSaveServers} style={{ width: "100%", marginTop: 8 }}>
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
                <Button variant="primary" size="sm" onClick={handleSave} style={{ width: "100%", marginTop: 8 }}>
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
