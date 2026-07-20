import {
    getControlServer
} from "../../network/control-server";
import {
    useCameraPositions,
    useControlServerStatus
} from "../../network/control-server";
import { Button } from "react-bootstrap";

/**
 * TODO finish this and use this somewhere
 */
function ControlServerStuff() {
    const status = useControlServerStatus();
    const positions = useCameraPositions();

    return (
        <>
            <Button onClick={() => getControlServer().connect()}>Connect</Button>
            <h3>Status</h3>
            <p style={{ whiteSpace: "pre-wrap", textAlign: "left" }}>
                {JSON.stringify(status, null, 2)}
            </p>
            <h3>Camera Positions</h3>
            <p style={{ whiteSpace: "pre-wrap", textAlign: "left" }}>
                {JSON.stringify(positions, null, 2)}
            </p>
        </>
    );
}