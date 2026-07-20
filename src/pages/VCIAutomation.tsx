import { useState } from "react";
import { Col, Row } from "react-bootstrap";
import { ScriptList } from "../Components/VCIAutomation/ScriptList";
import { useConnectionStatus, ServerStatusInfo } from "../network/interceptor";
import { getVCI } from "../network/vci-automation";
import { VCIAutomationScript } from "../Components/VCIAutomation/VCIAutomationScript";
import { ScriptInfo } from "../network/vci-automation";

export function VCIAutomationPage() {
    const status = useConnectionStatus(getVCI().socket);
    const [selectedScript, setSelectedScript] = useState<ScriptInfo | null>(null);

    return (
        <div
            className="d-flex justify-content-center"
            style={{ width: "100%" }}
        >
            <div style={{ width: "100%", maxWidth: 1600, minWidth: 0 }}>
                <h1 style={{ margin: "15px" }}>VCI Automation</h1>
                <ServerStatusInfo socket={getVCI().socket} />
                <Row className="mt-2 g-4 mx-0">
                    <Col xs={12} md={2} lg={2}>
                        <ScriptList onSelectScript={setSelectedScript} />
                    </Col>
                    <Col xs={12} md={10} lg={10}>
                        {selectedScript && <VCIAutomationScript key={selectedScript.id} script={selectedScript} />}
                    </Col>
                </Row>
            </div>
        </div>
    );
}
