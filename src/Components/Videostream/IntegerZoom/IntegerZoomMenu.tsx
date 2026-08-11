import { useKeyPress } from "../../../Utility/KeyBindings";
import { getServers } from "../../../network/capture-server";
import { leftIcon, rightIcon, upIcon, downIcon, zoomInIcon, zoomOutIcon, resetZoomIconFull, setZoom1_1Icon, resetZoomCenterIcon } from "../../shared/Icons.tsx";

export function useIntegerZoomKeyBindingsWebsocket(stream_id: string, server_id: number) {
  const category = "Integer Zoom";

  useKeyPress({
    key: "ArrowLeft",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: -1, y: 0 });
    },
    description: "Move Left",
    category: category,
    icon: leftIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowRight",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: 1, y: 0 });
    },
    description: "Move Right",
    category: category,
    icon: rightIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowUp",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: 0, y: -1 });
    },
    description: "Move Up",
    category: category,
    icon: upIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowDown",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.moveZoomCenterRel(stream_id, { x: 0, y: 1 });
    },
    description: "Move Down",
    category: category,
    icon: downIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "+",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.zoom_in(stream_id);
    },
    description: "Zoom In",
    category: category,
    icon: zoomInIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "-",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.zoom_out(stream_id);
    },
    description: "Zoom Out",
    category: category,
    icon: zoomOutIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "0",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.setZoomFactor(stream_id, 1);
    },
    description: "Zoom factor 1",
    category: category,
    icon: setZoom1_1Icon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "c",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.resetZoomCenter(stream_id);
    },
    description: "Center Zoom",
    category: category,
    icon: resetZoomCenterIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "r",
    onKeyEvent: () => {
      // getServers().getServer(server_id).resetZoom(stream_id);
    },
    description: "Reset Zoom",
    category: category,
    icon: resetZoomIconFull,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "f",
    onKeyEvent: () => {
      getServers().getServer(server_id)?.setStreamParameters(stream_id, { fix_full_size: true });
    },
    description: "Display the whole image",
    category: category,
    icon: resetZoomIconFull,
    dependencies: [stream_id, server_id],
  });
}

