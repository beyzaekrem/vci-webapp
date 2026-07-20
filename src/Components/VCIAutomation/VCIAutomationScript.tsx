import { Button, Col, Row } from "react-bootstrap";
import { getVCI, ScriptInfo } from "../../network/vci-automation";
import { ScriptInteractions } from "./ScriptInteractions";
import { ScriptArgumentsForm } from "./ScriptArgumentsForm";
import { useLocallyStored } from "../../Utility/Storage";
import { fullscreenIcon } from "../Icons";
import { ScriptOutput } from "./ScriptOutput";

export function VCIAutomationScript({ script }: { script: ScriptInfo }) {
    const [runnerId] = useLocallyStored<string>(`vci-automation-runner-${script.id}`, `runner-${Math.random().toString(16).slice(2)}`);

    return (
        <div className="mt-2">
            <h2 className="h4 text-start">{script.name}</h2>
            <Row className="g-4 align-items-start">
                <Col xs={12} lg={6}>
                    <ScriptArgumentsForm
                        scriptName={script.id}
                        onSubmit={(formData) => {
                            getVCI().run_script(script.id, runnerId, formData);
                        }}
                    />
                </Col>
                <Col xs={12} lg={6} className="position-relative">
                    <Button
                        as="a"
                        href={`/#/vci-automation/script_output/${runnerId}`}
                        target="_blank"
                        rel="noreferrer"
                        variant="outline-secondary"
                        size="sm"
                        className="position-absolute top-0 end-0"
                        style={{ zIndex: 1 }}
                    >
                        {fullscreenIcon} Fullscreen
                    </Button>
                    <Button
                        onClick={() => {
                            getVCI().stop_script(runnerId);
                        }}
                        variant="outline-danger"
                        size="sm"
                        className="position-absolute top-0 start-0"
                        style={{ zIndex: 1 }}
                    >
                        Stop Script
                    </Button>
                    <ScriptOutput runnerId={runnerId} />
                </Col>
            </Row>
        </div>
    );
}
