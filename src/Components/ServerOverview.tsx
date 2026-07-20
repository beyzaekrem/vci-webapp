import { Accordion } from "react-bootstrap";
import { getServers } from "../network/capture-server";
import { useSerialNumber, useCameraCount } from "../network/capture-server";
import { ServerStatusInfo as WebsocketStatusInfo } from "../network/interceptor";
import { InfoPopUpBadge } from "../Utility/UI";
import { NavLink } from "react-router-dom";
import { useToggleTriggerBox } from "./CameraHooks";

export function ServerOverview() {

    useToggleTriggerBox();

    return (
        <>
            <p>{getServers().servers.length} capture servers found. <br />
                Click <NavLink to="/config">here</NavLink> to edit the addresses.</p>
            <Accordion defaultActiveKey="0">
                {getServers().map((_, serverIndex) => {
                    return (
                        <ServerOverviewItem serverIndex={serverIndex} key={serverIndex} />
                    );
                })}
            </Accordion>
        </>
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
    const count = useCameraCount(serverIndex);
    return (
        <>
            <Accordion.Item eventKey={serverIndex + ""} key={serverIndex}>
                <Accordion.Header>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span>{getServers().getServer(serverIndex).getDomain()}</span>
                        <ServerStatusInfo serverIndex={serverIndex} />
                        <span>({count} cameras)</span>
                    </span>
                </Accordion.Header>
                <Accordion.Body style={{ padding: "0.5em" }}>
                    {Array(count)
                        .fill("aa")
                        .map((_, i) => {
                            return (
                                <div>
                                    Camera {i}: {"   "}
                                    <SerialNumberInfo serverIndex={serverIndex} camIndex={i} />
                                </div>
                            );
                        })}
                </Accordion.Body>
            </Accordion.Item>
        </>
    );
}

function ServerStatusInfo({ serverIndex }: { serverIndex: number }) {
    return (
        <WebsocketStatusInfo
            socket={getServers().getServer(serverIndex).socket}
        />
    );
}
