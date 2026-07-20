/**
 * This module defines custom React hooks for managing and retrieving data from capture server connections.
 * Utilizes the singleton instance of CaptureServers
 * to access camera system data and connection status. 
 * The hooks in this module do not need the CaptureServer class, only CaptureServerConnection (unlike CameraHooks.tsx)
 * @packageDocumentation
 */

import { useEffect, useState } from "react";
import {
  CameraSystemData,
  Param,
  Params,
} from "./CameraSystemData.tsx";
import { CaptureServerConnection } from "./CaptureServerConnection.tsx";
import { getServers } from "./CaptureServersSingleton";

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
 * Retrieves a specific parameter from the camera information
 * of a given server and camera index.
 *
 * @param serverIndex - The index of the server from which to retrieve the camera information.
 * @param camIndex - The index of the camera within the server's camera parameters.
 * @param getParam - A function that extracts the desired parameter from the camera's parameters.
 * @returns The extracted parameter, or a default value ("unknown") if the parameter is not available.
 */
export function useParameter(
  serverIndex: number,
  camIndex: number,
  getParam: (cam: Params) => any,
): Param {
  const p = useCameraInfoProperty(
    serverIndex,
    (o) => getParam(o.camera_parameters[camIndex]),
    "unknown",
  );
  return p;
}

/**
 * Retrieve the serial number of a camera from a specific server and camera index.
 *
 * @param serverIndex - The index of the server to query.
 * @param camIndex - The index of the camera within the server to retrieve the serial number for.
 * @returns The serial number of the specified camera, or "unknown" if unavailable.
 */
export function useSerialNumber(serverIndex: number, camIndex: number): string {
  //const p = useWebSocketProperty(serverIndex, o => o.camera_parameters[camIndex].device_sn.value, "unknown")
  const p = useCameraInfoProperty(
    serverIndex,
    (o) => o.serial_numbers.by_index[camIndex],
    "unknown",
  );
  return p;
}

/**
 * A custom hook that retrieves a specific field from the camera system data
 * for all servers using WebSocket connections.
 *
 * @template T - The type of the field to be retrieved.
 * @param getField - A function that extracts the desired field from the 
 *                   camera system data for a given server index.
 * @returns An array of values of type `T`, where each value corresponds to 
 *          the extracted field for a server.
 */
function useWebsocketFieldForAllServers<T>(
  getField: (c: CameraSystemData, serverIndex: number) => T,
): T[] {
  const vals = getServers().map((server, serverIndex) => {

    const ws = useCameraInfoProperty(
      serverIndex,
      (c) => c,
      {} as CameraSystemData,
    );
    return getField(ws, serverIndex);
  });
  return vals;
}

/**
 * Hook to get the indices of all cameras across all servers.
 * @returns An array of tuples, where each tuple contains the server index and camera index.
 */
export function useCameraIndices(): number[][] {
  const c = useWebsocketFieldForAllServers((cam) =>
    cam && cam.serial_numbers
      ? Object.keys(cam.serial_numbers.by_index).length
      : 0,
  );
  const cameras = c.flatMap((camCount, serverIndex) =>
    new Array(camCount).fill(0).map((_, i) => [serverIndex, i]),
  );
  return cameras;
}

/**
 * Hook to get a property from the camera info.
 * @param serverIndex The index of the server.
 * @param getProperty A function that takes the camera info and returns the desired property.
 * @param defaultValue The default value to return if the property is not found.
 * @returns The value of the property.
 * @template T The type of the property.
 */

export function useCameraInfoProperty<T>(
  serverIndex: number,
  getProperty: (c: CameraSystemData) => T,
  defaultValue: T
): T {
  const ws = getServers().getServer(serverIndex).socket

  const obj = useWebSocketAttribute({
    webSocketConnection: ws,
    getProperty: getProperty,
    defaultValue: defaultValue,
  });

  return obj;
}

/**
 * Retrieves a specific attribute from the camera system data of a WebSocket connection.
 * @param webSocketConnection The capture server connection to read from.
 * @param defaultValue The fallback value before data arrives.
 * @param getProperty Selector function to read a property from CameraSystemData.
 * @returns The selected property value.
 */
function useWebSocketAttribute({
  webSocketConnection, defaultValue = -1, getProperty,
}: {
  webSocketConnection: CaptureServerConnection;
  defaultValue?: any;
  getProperty: (c: CameraSystemData) => any;
}): any {
  const [data, setData] = useState(defaultValue);
  const ws = webSocketConnection;

  useEffect(() => {
    ws.getSocketEvents().addEventListener("newMessageData", setNewData);

    //call setNewData for getProperty with last message if this is called after a message is received
    if(ws.getCurrentCamToolState() != undefined) {
      setNewData();
    }

    return () => {
      ws.getSocketEvents().removeEventListener("newMessageData", setNewData);
    };
  }, [getProperty, ws]);

  function setNewData() {
    const state = ws.getCurrentCamToolState();

    if(state == undefined) {
      console.warn("current cam tool state is undefined, cannot get new data yet.");
      return;
      /*cam tool state gets updated in a newMessageData event of InterceptorConnection.
      setNewData gets also called in a newMessageData event (which is practically equivalent to onNewMessage function).
      If cam tool state is updated after this event is triggered, we might end up here.
      TODO This has never been a problem but see if there is a better way to handle this
      */
    }

    try {
      var newValue = getProperty(state);
      setData((oldValue: any) => {
        //only update values in nested obj if they arent equal
        //if(!deepEqual(oldValue, newValue)){
        return newValue;
      });
    } catch(e) {
      console.warn(e);
    }
  }

  return data;
}
