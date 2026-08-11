import { useState } from "react";
import Select from "react-select";
import { ButtonWithKey, useKeyPress } from "../../../Utility/KeyBindings";
import { useCameraIndices } from "../../../network/capture-server";
import { getServers } from "../../../network/capture-server";
import { Button } from "react-bootstrap";
import { nextItem, previousItem } from "../../shared/Icons.tsx";
import { useCameraSelections, CameraSelection } from "./useCameraSelections.ts";

/*------------------------------------------------------------------------------
  GENERALIZED SELECTION COMPONENT
------------------------------------------------------------------------------*/

export interface SelectionProps {
  selectionKey?: string;
  storage?: "url" | "local"
  isMulti?: boolean;
}

/**
 * A generalized camera selection component.
 * If **isMulti** is true, multiple selections are allowed; otherwise only one selection is used.
 * In all cases the underlying selection state is an array (of one element when isMulti is false).
 *
 * Props:
 * - isMulti: whether to allow multiple selections (default false)
 * - storage: "url" or "local" (default "url")
 * - selectionKey: the key name used for URL/local storage (default "cameras")
 */
export function SelectCameras({
  isMulti = false,
  storage = "url",
  selectionKey = "cameras",
}: SelectionProps) {
  return isMulti ? (
    <SelectMultipleCameras storage={storage} selectionKey={selectionKey} />
  ) : (
    <SelectSingleCamera storage={storage} selectionKey={selectionKey} />
  );
}

/*------------------------------------------------------------------------------
  SINGLE CAMERA SELECTION UI COMPONENT
  (Internally, the selection is always an array with one element)
------------------------------------------------------------------------------*/

/**
 * A component that lets the user select a single camera.
 * Even though only one selection is active, the underlying state is an array.
 *
 * Props:
 * - storage: "url" or "local"
 * - selectionKey: the key name to use (default "cameras")
 */
function SelectSingleCamera({
  storage = "url",
  selectionKey = "cameras",
}: {
  storage?: "url" | "local";
  selectionKey?: string;
}) {
  const [selections, setSelections] = useCameraSelections({ storage, selectionKey });
  // Ensure there is always one selection.
  const selection = selections[0] || { server: 0, camera: 0 };

  const updateSelection = (newSel: CameraSelection) => {
    setSelections([newSel]);
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: "4px", maxWidth: "100%" }}>
      <MoveCameraIndexButtonSingle increment={-1} selection={selection} setSelection={updateSelection} />
      <SelectCameraDropdownSingle selection={selection} setSelection={updateSelection} />
      <MoveCameraIndexButtonSingle increment={1} selection={selection} setSelection={updateSelection} />
    </div>
  );
}

function MoveCameraIndexButtonSingle({
  increment,
  selection,
  setSelection,
}: {
  increment: number;
  selection: CameraSelection;
  setSelection: (sel: CameraSelection) => void;
}) {
  const key = increment > 0 ? "e" : "w";
  const icon = increment > 0 ? nextItem : previousItem;
  const cameras = useCameraIndices();

  function move() {
    const currentIndex = cameras.findIndex(
      ([server, camera]) =>
        server === selection.server && camera === selection.camera
    );
    const newIndex = (currentIndex + increment + cameras.length) % cameras.length;
    const [newServer, newCamera] = cameras[newIndex];
    setSelection({ server: newServer, camera: newCamera });
  }

  useKeyPress({
    key,
    description: increment > 0 ? "Next Camera" : "Previous Camera",
    onKeyEvent: move,
    category: "General",
    icon,
    dependencies: [cameras, selection],
  });

  return <ButtonWithKey keybinding={key} />;
}

function SelectServerDropdownSingle({
  selection,
  setSelection,
}: {
  selection: CameraSelection;
  setSelection: (sel: CameraSelection) => void;
}) {
  const servers = getServers();
  const options = (servers?.servers || []).map((server, index) => ({
    value: index,
    label: `Server ${index + 1} (${server?.getDomain() || "127.0.0.1"})`,
  }));
  const currentValue = options.find((option) => option.value === selection.server);
  const allCameras = useCameraIndices();
  return (
    <div style={{ zIndex: 200, minWidth: "120px", flex: "1 1 auto" }}>
      <Select
        options={options}
        value={currentValue}
        onChange={(v) => {
          if(!v) return;
          const newServer = v.value;
          const newCameras = allCameras.filter(([s]) => s === newServer);
          const newCamera = newCameras.length > 0 ? newCameras[0][1] : 0;
          setSelection({ server: newServer, camera: newCamera });
        }}
      />
    </div>
  );
}

function SelectCameraIndexSingle({
  selection,
  setSelection,
}: {
  selection: CameraSelection;
  setSelection: (sel: CameraSelection) => void;
}) {
  const allCameras = useCameraIndices();
  const camerasForServer = allCameras.filter(([s]) => s === selection.server);
  const serverObj = getServers().getServer(selection.server);
  const options = camerasForServer.map(([_, camera]) => {
    const shorthand = serverObj ? serverObj.getCamera(camera)?.getShorthand() : undefined;
    const shorthandText = shorthand ? ` (${shorthand})` : "";
    return {
      value: camera,
      label: `Camera ${camera + 1}${shorthandText}`,
    };
  });
  const currentValue = options.find((option) => option.value === selection.camera);
  return (
    <div style={{ zIndex: 200, minWidth: "110px", flex: "1 1 auto" }}>
      <Select
        options={options}
        value={currentValue}
        onChange={(v) => {
          if(!v) return;
          setSelection({ ...selection, camera: v.value });
        }}
      />
    </div>
  );
}

function SelectCameraDropdownSingle({
  selection,
  setSelection,
}: {
  selection: CameraSelection;
  setSelection: (sel: CameraSelection) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: "4px", maxWidth: "100%" }}>
      <SelectServerDropdownSingle selection={selection} setSelection={setSelection} />
      <SelectCameraIndexSingle selection={selection} setSelection={setSelection} />
    </div>
  );
}

/*------------------------------------------------------------------------------
  MULTIPLE CAMERA SELECTION UI COMPONENT
------------------------------------------------------------------------------*/

/**
 * A component that lets the user select multiple cameras.
 *
 * Props:
 * - storage: "url" or "local"
 * - selectionKey: the key name to use (default "cameras")
 */
function SelectMultipleCameras({
  storage = "url",
  selectionKey = "cameras",
}: {
  storage?: "url" | "local";
  selectionKey?: string;
}) {
  const [selections, setSelections] = useCameraSelections({ storage, selectionKey });
  const camerasAll = useCameraIndices();
  const servers = getServers();

  // State for "Add All Cameras" dropdown
  const [selectedServerForAll, setSelectedServerForAll] = useState<number>(0);
  const addAllServerOptions = (servers?.servers || []).map((server, index) => {
    const cameraCount = camerasAll.filter(([s]) => s === index).length;
    return {
      value: index,
      label: `Server ${index + 1} (${server?.getDomain() || "127.0.0.1"}) - ${cameraCount} camera${cameraCount !== 1 ? "s" : ""}`,
    };
  });

  return (
    <div>
      {selections.map((sel, index) => (
        <CameraSelectionRow
          key={index}
          selection={sel}
          onUpdate={(newSel) =>
            setSelections(selections.map((s, i) => (i === index ? newSel : s)))
          }
          onRemove={() => setSelections(selections.filter((_, i) => i !== index))}
        />
      ))}
      <div style={{ marginTop: "16px", marginBottom: "16px" }}>
        <Button
          onClick={() => {
            const defaultServer = 0;
            const newCameras = camerasAll.filter(([server]) => server === defaultServer);
            const defaultCamera = newCameras.length > 0 ? newCameras[0][1] : 0;
            setSelections([...selections, { server: defaultServer, camera: defaultCamera }]);
          }}
        >
          Add Camera
        </Button>
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "16px" }}>
        <div style={{ marginRight: "8px", minWidth: "200px" }}>
          <Select
            options={addAllServerOptions}
            value={addAllServerOptions.find((option) => option.value === selectedServerForAll)}
            onChange={(v) => {
              if(!v) return;
              setSelectedServerForAll(v.value);
            }}
          />
        </div>
        <Button
          onClick={() => {
            const allCamerasForServer = camerasAll.filter(
              ([server]) => server === selectedServerForAll
            );
            if(allCamerasForServer.length === 0) return;
            setSelections([
              ...selections,
              ...allCamerasForServer.map(([server, camera]) => ({ server, camera })),
            ]);
          }}
        >
          Add All Cameras
        </Button>
      </div>
      <div style={{ textAlign: "center" }}>
        <Button onClick={() => setSelections([])}>Clear Selection</Button>
      </div>
    </div>
  );
}

function CameraSelectionRow({
  selection,
  onUpdate,
  onRemove,
}: {
  selection: CameraSelection;
  onUpdate: (newSelection: CameraSelection) => void;
  onRemove: () => void;
}) {
  const servers = getServers();
  const serverOptions = (servers?.servers || []).map((server, index) => ({
    value: index,
    label: `Server ${index + 1} (${server?.getDomain() || "127.0.0.1"})`,
  }));
  const allCameras = useCameraIndices();
  const camerasForServer = allCameras.filter(([server]) => server === selection.server);
  const cameraOptions = camerasForServer.map(([_, camera]) => ({
    value: camera,
    label: `Camera ${camera + 1}`,
  }));
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: "8px",
      }}
    >
      <div style={{ marginRight: "8px", minWidth: "200px" }}>
        <Select
          options={serverOptions}
          value={serverOptions.find((option) => option.value === selection.server)}
          onChange={(v) => {
            if(!v) return;
            const newServer = v.value;
            const allCameras = useCameraIndices();
            const newCameras = allCameras.filter(([s]) => s === newServer);
            const newCamera = newCameras.length > 0 ? newCameras[0][1] : 0;
            onUpdate({ server: newServer, camera: newCamera });
          }}
        />
      </div>
      <div style={{ marginRight: "8px", minWidth: "200px" }}>
        <Select
          options={cameraOptions}
          value={cameraOptions.find((option) => option.value === selection.camera)}
          onChange={(v) => {
            if(!v) return;
            onUpdate({ server: selection.server, camera: v.value });
          }}
        />
      </div>
      <Button onClick={onRemove}>Remove</Button>
    </div>
  );
}

