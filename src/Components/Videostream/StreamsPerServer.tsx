import { useEffect } from "react";
import { useLocallyStored } from "../../Utility/Storage";
import { useCameraIndices } from "../../network/capture-server";
import { getServers } from "../../network/capture-server";
import { SelectServer } from "../shared/SelectServer.tsx";
import { GridWithFocusedElement } from "./WebsocketGrid.tsx";

export function StreamsPerServer() {
  const storageKey = "currentServerForVideostreams";
  const [serverIndex, setServer] = useLocallyStored<number>(storageKey, 0);
  const cameras = useCameraIndices();

  // Switch the active server to livestream mode when this component mounts
  // or when the user selects a different server
  useEffect(() => {
    const servers = getServers();
    if (serverIndex >= 0 && serverIndex < servers.servers.length) {
      servers.getServer(serverIndex)?.switchMode("livestream");
    }
  }, [serverIndex]);

  const camerasFromServer = cameras.filter(
    ([server, _]) => server === serverIndex,
  );

  const streams = camerasFromServer.map(([server, camera]) => {
    return { serverIndex: server, cameraIndex: camera, streamID: "streamsPerServer" + camera };
  })

  if(serverIndex < 0 || serverIndex >= getServers().servers.length) {
    return (
      <div style={{ textAlign: "center", marginTop: "2rem" }}>
        <p>Server {serverIndex} not found. Please select a valid server from the menu below:</p>
        <div style={{ height: "3vh", display: "flex", alignItems: "center", justifyContent: "center", marginTop: "1rem" }}>
          <SelectServer serverIdKey={storageKey} />
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        style={{
          height: "3vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <SelectServer serverIdKey={storageKey} />
      </div>
      <div style={{ height: "100%" }}>
        <GridWithFocusedElement streams={streams} />
      </div>
    </>
  );
}
