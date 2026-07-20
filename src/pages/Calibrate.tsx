import { useEffect, useState } from "react";
import { SelectCameras } from "../Components/SelectCameras";
import { useCameraSelectionsReadOnly } from "../Components/SelectCameras";
import { useExposureKeyBindings, useToggleTriggerSourceKeyBindings } from "../Components/CameraHooks";
import { ContextMenu } from "../Utility/KeyBindings";
import { useCameraIndices } from "../network/capture-server";
import { Grid, useIntegerZoomKeyBindingsWebsocket } from "../Components/Videostream";
import { useClientID } from "../Utility/Storage";

export function Calibrate() {
  const clientID = useClientID();

  const storage = "local";
  const selectionKey = "cameraForCalibration"
  const currentCam = useCameraSelectionsReadOnly({ storage: storage, selectionKey: selectionKey })[0] || { server: 0, camera: 0 };

  useExposureKeyBindings(currentCam.server, currentCam.camera);

  useToggleTriggerSourceKeyBindings(currentCam.server, currentCam.camera);

  // Set the stream IDs for the main and zoomed stream
  // We need to use the client ID to ensure that multiple people do not share the same stream ID
  const [streamIDs, setStreamIDs] = useState<{ zoomedStreamId: string | null, mainStreamId: string | null }>({ zoomedStreamId: null, mainStreamId: null });
  useEffect(() => {
    setStreamIDs({
      zoomedStreamId: clientID + "_calibrationZoomedStreamId_" + currentCam.camera,
      mainStreamId: clientID + "_calibrationMainStreamId_" + currentCam.camera
    });
  }, [currentCam, clientID]);

  useIntegerZoomKeyBindingsWebsocket(streamIDs.zoomedStreamId || "", currentCam.server);


  const cameras = useCameraIndices();
  if(cameras.length === 0) return <div>Loading...</div>;

  const streams = [
    { serverIndex: currentCam.server!, cameraIndex: currentCam.camera!, streamID: streamIDs.mainStreamId! },
    { serverIndex: currentCam.server!, cameraIndex: currentCam.camera!, streamID: streamIDs.zoomedStreamId! }
  ]

  return (
    <div>
      <div style={{ width: "100vw", height: "100vh" }}>
        <SelectCameras storage={storage} selectionKey={selectionKey} />
        <div style={{ position: "relative" }}>
          <div className="d-flex justify-content-center">
            <ContextMenu category="Camera" />
            <ContextMenu category="Integer Zoom" />
          </div>
          {
            streamIDs.zoomedStreamId && streamIDs.mainStreamId &&
            <div style={{ position: "relative", width: "100%", height: "90vh" }}>
              <Grid streams={streams} />
            </div>
          }
        </div>
      </div>
    </div>
  );
}
