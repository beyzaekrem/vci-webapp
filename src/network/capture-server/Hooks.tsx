/**
 * Custom React hooks for managing and retrieving data from capture server connections.
 * Utilizes the singleton instance of CaptureServers
 * to access camera system data and connection status.
 * @packageDocumentation
 */

import { useEffect, useState } from "react";
import { CameraSystemData, Param, Params } from "./CameraSystemData";
import { CaptureServerConnection } from "./CaptureServerConnection";
import { getServers } from "./CaptureServersSingleton";
import { Message } from "../interceptor";

/**
 * Hook to get the number of cameras for a given server.
 * @param serverIndex The index of the server.
 * @returns The number of cameras.
 */
export function useCameraCount(serverIndex: number): number {
  const count = useCameraInfoProperty(serverIndex, (o) => o.camera_count, 0);
  return count;
}

/**
 * Retrieve the serial number of a camera from a specific server and camera index.
 * @param serverIndex The index of the server.
 * @param camIndex The index of the camera within the server.
 * @returns The serial number of the specified camera, or "unknown".
 */
export function useSerialNumber(serverIndex: number, camIndex: number): string {
  const p = useCameraInfoProperty(
    serverIndex,
    (o) => o?.serial_numbers?.by_index?.[camIndex],
    "unknown",
  );
  return p || "unknown";
}

/**
 * Retrieves a specific parameter from the camera information
 * of a given server and camera index.
 */
export function useParameter(
  serverIndex: number,
  camIndex: number,
  getParam: (cam: Params) => any,
): any {
  return useCameraInfoProperty(
    serverIndex,
    (camInfo) => {
      const cameraParams = camInfo.camera_parameters?.[camIndex];
      return cameraParams ? getParam(cameraParams) : undefined;
    },
    "unknown",
  );
}

/**
 * Retrieves the parameter info object from the camera parameters
 * of a given server and camera index.
 */
export function useParameterParam(
  serverIndex: number,
  camIndex: number,
  getParam: (cam: Params) => Param,
): Param | undefined {
  return useCameraInfoProperty(
    serverIndex,
    (camInfo) => {
      const cameraParams = camInfo.camera_parameters?.[camIndex];
      return cameraParams ? getParam(cameraParams) : undefined;
    },
    undefined,
  );
}

/**
 * Hook to get a property from the camera info of a server.
 */
export function useCameraInfoProperty<T>(
  serverIndex: number,
  getProperty: (c: CameraSystemData) => T,
  defaultValue: T,
): T {
  let ws: CaptureServerConnection | undefined = undefined;
  try {
    const server = getServers().getServer(serverIndex);
    ws = server ? server.socket : undefined;
  } catch {
    // Server singleton not ready
  }

  const obj = useWebSocketAttribute({
    webSocketConnection: ws,
    getProperty: getProperty,
    defaultValue: defaultValue,
  });

  return obj;
}

/**
 * Retrieves a specific attribute from the camera system data of a WebSocket connection.
 */
function useWebSocketAttribute<T>({
  webSocketConnection,
  defaultValue,
  getProperty,
}: {
  webSocketConnection: CaptureServerConnection | undefined;
  defaultValue: T;
  getProperty: (c: CameraSystemData) => T;
}): T {
  const [data, setData] = useState<T>(defaultValue);
  const ws = webSocketConnection;

  useEffect(() => {
    if (!ws) return;

    function setNewData() {
      if (!ws) return;
      const state = ws.getCurrentCamToolState();
      if (state === undefined) {
        return;
      }

      try {
        const newValue = getProperty(state);
        if (newValue !== undefined) {
          setData(newValue);
        }
      } catch (e) {
        // Ignore extraction error before full payload arrives
      }
    }

    const listener = (msg: Message) => {
      if (msg.PATH === "GET_ALL_INFO" || msg.PATH === "SWITCH_MODE") {
        setNewData();
      }
    };

    ws.addListener(listener);

    if (ws.getCurrentCamToolState() !== undefined) {
      setNewData();
    }

    return () => {
      ws.removeListener(listener);
    };
  }, [getProperty, ws]);

  return data;
}

/**
 * A custom hook that retrieves a specific field from the camera system data
 * for all servers using WebSocket connections.
 */
function useWebsocketFieldForAllServers<T>(
  getField: (c: CameraSystemData, serverIndex: number) => T,
): T[] {
  let serversCount = 0;
  try {
    serversCount = getServers().servers.length;
  } catch {
    // Singleton not ready
  }

  const vals: T[] = [];
  for (let i = 0; i < serversCount; i++) {
    const ws = useCameraInfoProperty(
      i,
      (c) => getField(c, i),
      {} as T,
    );
    vals.push(ws);
  }
  return vals;
}

/**
 * Hook to get the indices of all cameras across all servers.
 * @returns An array of tuples [serverIndex, cameraIndex]
 */
export function useCameraIndices(): [number, number][] {
  const c = useWebsocketFieldForAllServers((cam) =>
    cam && cam.serial_numbers && cam.serial_numbers.by_index
      ? Object.keys(cam.serial_numbers.by_index).length
      : 0,
  );
  const cameras = c.flatMap((camCount, serverIndex) =>
    new Array(camCount).fill(0).map((_, i): [number, number] => [serverIndex, i]),
  );
  return cameras;
}
