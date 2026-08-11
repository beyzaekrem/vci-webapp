import { useEffect, useMemo } from "react";
import { SelectCameras, useCameraSelections } from "../Components/features/SelectCameras";
import { useExposureKeyBindings, useToggleTriggerSourceKeyBindings } from "../Components/features/CameraHooks";
import { ContextMenu } from "../Utility/KeyBindings";
import { useCameraIndices, getServers } from "../network/capture-server";
import { Grid, useIntegerZoomKeyBindingsWebsocket } from "../Components/Videostream";
import { useClientID } from "../Utility/Storage";
import { ServerStatusButton } from "../Components/shared/ServerStatusModal";

export function Calibrate() {
  const clientID = useClientID();

  const storage = "local";
  const selectionKey = "cameraForCalibration";
  const [selections, setSelections] = useCameraSelections({ storage, selectionKey });
  const cameras = useCameraIndices();

  // Auto-select first available camera if no selection exists
  useEffect(() => {
    if (selections.length === 0 && cameras.length > 0) {
      const [firstServer, firstCam] = cameras[0];
      setSelections([{ server: firstServer, camera: firstCam }]);
    }
  }, [selections, cameras, setSelections]);

  const currentCam = selections[0] || (cameras.length > 0 ? { server: cameras[0][0], camera: cameras[0][1] } : { server: 0, camera: 0 });

  const serverIndex = currentCam.server ?? 0;
  const cameraIndex = currentCam.camera ?? 0;

  // Stable stream ID generation using primitive dependencies
  const mainStreamId = useMemo(() => {
    return `${clientID}_calibrationMainStream_${serverIndex}_${cameraIndex}`;
  }, [clientID, serverIndex, cameraIndex]);

  const zoomedStreamId = useMemo(() => {
    return `${clientID}_calibrationZoomedStream_${serverIndex}_${cameraIndex}`;
  }, [clientID, serverIndex, cameraIndex]);

  // Ensure server is switched to livestream mode
  useEffect(() => {
    const server = getServers().getServer(serverIndex);
    server?.switchMode("livestream");
  }, [serverIndex]);

  useExposureKeyBindings(serverIndex, cameraIndex);
  useToggleTriggerSourceKeyBindings(serverIndex, cameraIndex);
  useIntegerZoomKeyBindingsWebsocket(zoomedStreamId, serverIndex);

  const streams = useMemo(() => [
    { serverIndex, cameraIndex, streamID: mainStreamId },
    { serverIndex, cameraIndex, streamID: zoomedStreamId }
  ], [serverIndex, cameraIndex, mainStreamId, zoomedStreamId]);

  if (cameras.length === 0) {
    return (
      <div className="ps-content-wrapper">
        <header className="ps-header-bar">
          <h1 className="ps-header-title">Calibrate</h1>
          <ServerStatusButton />
        </header>
        <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>
          Loading camera configuration...
        </div>
      </div>
    );
  }

  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar">
        <h1 className="ps-header-title">Calibrate</h1>
        <ServerStatusButton />
      </header>

      {/* Main Layout Area */}
      <main className="cal-main-area" style={{ flex: 1, padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px", minHeight: 0, overflow: "auto" }}>
        {/* Top Control Bar Card */}
        <div className="cal-control-card" style={{
          backgroundColor: "#ffffff",
          borderRadius: "12px",
          border: "1px solid #e2e8f0",
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "16px",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Camera Selection:
            </span>
            <SelectCameras storage={storage} selectionKey={selectionKey} />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <ContextMenu category="Camera" />
            <ContextMenu category="Integer Zoom" />
          </div>
        </div>

        {/* Video Streams Container Card */}
        <div className="cal-stream-card">
          <div style={{ flex: 1, position: "relative", width: "100%", height: "100%" }}>
            <Grid streams={streams} />
          </div>
        </div>
      </main>
    </div>
  );
}
