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
        <div style={{ padding: 16, maxWidth: 350 }}>
            <ControlServerAddressSection />
            <VCIAutomationSection />
            <ServerAddressesSection />

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

    /**
     * Save the new control server address.
     */
    const handleSave = () => {
        setControlServerConfig({
            ...controlServerConfig,
            address: addressInput,
        });
        window.location.reload(); // Reload to apply changes
    };

    return (
        <div style={{ marginBottom: 32 }}>
            <h3>Control Server</h3>
            <h4>Address</h4>
            <input
                type="text"
                value={addressInput}
                onChange={e => setAddressInput(e.target.value)}
                placeholder="Enter IP address"
                style={{ width: "100%", marginBottom: 8 }}
            />
            <Button onClick={handleSave} style={{ width: "100%", marginBottom: 16 }}>
                Save
            </Button>
            <h4>Port</h4>
            <input
                type="text"
                value={controlServerConfig.port || ""}
                onChange={e => {
                    setControlServerConfig({ ...controlServerConfig, port: parseInt(e.target.value) || undefined })
                    reloadControlServer();
                }}
                placeholder="Port number (default 2443)"
                style={{ width: "100%", marginBottom: 8, fontFamily: "monospace" }}
            />
            <h4>Route</h4>
            <input
                type="text"
                value={controlServerConfig.route || ""}
                onChange={e => {
                    setControlServerConfig({ ...controlServerConfig, route: e.target.value || undefined });
                    reloadControlServer();
                }}
                placeholder="Route (default /websocket)"
                style={{ width: "100%", marginBottom: 8, fontFamily: "monospace" }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>
                Current: <b>{controlServerConfig.address}</b>
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

    /**
     * Save the new list of server addresses.
     * Splits input by lines, trims, and filters out empty lines.
     * Reloads the page to apply changes.
     */
    const handleSaveServers = () => {
        const addresses = serverAddressesInput
            .split(/\r?\n/)
            .map(addr => addr.trim())
            .filter(addr => addr.length > 0);
        setCaptureServerConfig({ ...captureServerConfig, addresses });
        window.location.reload();
    };

    return (
        <div>
            <h3>Capture Servers</h3>
            <h4>Addresses</h4>
            <textarea
                value={serverAddressesInput}
                onChange={e => setServerAddressesInput(e.target.value)}
                placeholder="One IP per line"
                rows={serverAddresses.length || 8}
                style={{ width: "100%", marginBottom: 8, fontFamily: 'monospace' }}
            />
            <Button onClick={handleSaveServers} style={{ width: "100%" }}>
                Save Server Addresses
            </Button>
            <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>
                Current:<br />
                {serverAddresses.map((addr, i) => (
                    <div key={i}><b>{addr}</b></div>
                ))}
            </div>
            <h4>Port</h4>
            <textarea
                value={captureServerConfig.port || ""}
                onChange={e => {
                    setCaptureServerConfig({ ...captureServerConfig, port: parseInt(e.target.value) || undefined })
                    reloadCaptureServers();
                }}
                placeholder="Port number (default 2443)"
                rows={1}
                style={{ width: "100%", marginBottom: 8, fontFamily: 'monospace' }}
            />
            <h4>Route</h4>
            <textarea
                value={captureServerConfig.route || ""}
                onChange={e => {
                    setCaptureServerConfig({ ...captureServerConfig, route: e.target.value || undefined });
                    reloadCaptureServers();
                }}
                placeholder="Route (default /websocket)"
                rows={1}
                style={{ width: "100%", marginBottom: 8, fontFamily: 'monospace' }}
            />

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
        <div style={{ marginBottom: 32 }}>
            <h3>VCI Automation</h3>
            <h4>Address</h4>
            <input
                type="text"
                value={addressInput}
                onChange={e => setAddressInput(e.target.value)}
                placeholder="Enter IP address"
                style={{ width: "100%", marginBottom: 8 }}
            />
            <Button onClick={handleSave} style={{ width: "100%", marginBottom: 16 }}>
                Save
            </Button>
            <h4>Port</h4>
            <input
                type="text"
                value={vciConfig.port || ""}
                onChange={e => {
                    setVciConfig({ ...vciConfig, port: parseInt(e.target.value) || undefined });
                    reloadVCI();
                }}
                placeholder="Port number (default 2525)"
                style={{ width: "100%", marginBottom: 8, fontFamily: "monospace" }}
            />
            <h4>Route</h4>
            <input
                type="text"
                value={vciConfig.route || ""}
                onChange={e => {
                    setVciConfig({ ...vciConfig, route: e.target.value || undefined });
                    reloadVCI();
                }}
                placeholder="Route"
                style={{ width: "100%", marginBottom: 8, fontFamily: "monospace" }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>
                Current: <b>{vciConfig.address}</b>
            </div>
        </div>
    );
}

