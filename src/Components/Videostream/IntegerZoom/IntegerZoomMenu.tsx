import { useKeyPress } from "../../../Utility/KeyBindings";
import { getServers } from "../../../network/capture-server";
import { leftIcon, rightIcon, upIcon, downIcon, zoomInIcon, zoomOutIcon, resetZoomIconFull, setZoom1_1Icon, resetZoomCenterIcon } from "../../shared/Icons.tsx";

const MOVE_STEP = 0.05; // Fine 0.05 normalized shift (0.05 * 200 = 10px shift on Python backend)

export function useIntegerZoomKeyBindingsWebsocket(stream_id: string, server_id: number) {
  const category = "Integer Zoom";

  useKeyPress({
    key: ["ArrowLeft", "a", "A"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: -MOVE_STEP, y: 0 });
    },
    description: "Move Left (Fine)",
    category: category,
    icon: leftIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["ArrowRight", "d", "D"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: MOVE_STEP, y: 0 });
    },
    description: "Move Right (Fine)",
    category: category,
    icon: rightIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["ArrowUp", "w", "W"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: 0, y: -MOVE_STEP });
    },
    description: "Move Up (Fine)",
    category: category,
    icon: upIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["ArrowDown", "s", "S"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: 0, y: MOVE_STEP });
    },
    description: "Move Down (Fine)",
    category: category,
    icon: downIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["+", "=", "Equal", "NumpadAdd"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.zoom_in(stream_id);
    },
    description: "Zoom In (+)",
    category: category,
    icon: zoomInIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["-", "Minus", "NumpadSubtract"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.zoom_out(stream_id);
    },
    description: "Zoom Out (-)",
    category: category,
    icon: zoomOutIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["r", "R"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.setZoomFactor(stream_id, 1);
      getServers().getServer(server_id)?.resetZoomCenter(stream_id);
    },
    description: "Reset Zoom & Center",
    category: category,
    icon: resetZoomIconFull,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["c", "C"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.resetZoomCenter(stream_id);
    },
    description: "Center Zoom View",
    category: category,
    icon: resetZoomCenterIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: ["f", "F"],
    onKeyEvent: () => {
      getServers().getServer(server_id)?.setStreamParameters(stream_id, { fix_full_size: true });
    },
    description: "Fit Screen (Full View)",
    category: category,
    icon: setZoom1_1Icon,
    dependencies: [stream_id, server_id],
  });
}
