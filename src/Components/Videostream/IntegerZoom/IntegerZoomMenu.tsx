import { useKeyPress } from "../../../Utility/KeyBindings";
import { getServers } from "../../../network/capture-server";
import { leftIcon, rightIcon, upIcon, downIcon, zoomInIcon, zoomOutIcon, resetZoomIconFull, setZoom1_1Icon, resetZoomCenterIcon } from "../../Icons.tsx";

export function useIntegerZoomKeyBindingsWebsocket(stream_id: string, server_id: number) {
  const category = "Integer Zoom";

  useKeyPress({
    key: "ArrowLeft",
    onKeyEvent: () => {
      getServers().getServer(server_id).moveZoomCenterRel(stream_id, { x: -1, y: 0 });
    },
    description: "Move Left",
    category: category,
    icon: leftIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowRight",
    onKeyEvent: () => {
      getServers().getServer(server_id).moveZoomCenterRel(stream_id, { x: 1, y: 0 });
    },
    description: "Move Right",
    category: category,
    icon: rightIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowUp",
    onKeyEvent: () => {
      getServers().getServer(server_id).moveZoomCenterRel(stream_id, { x: 0, y: -1 });
    },
    description: "Move Up",
    category: category,
    icon: upIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "ArrowDown",
    onKeyEvent: () => {
      getServers().getServer(server_id).moveZoomCenterRel(stream_id, { x: 0, y: 1 });
    },
    description: "Move Down",
    category: category,
    icon: downIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "PageUp",
    onKeyEvent: () => {
      getServers().getServer(server_id).zoom_in(stream_id);
    },
    description: "Zoom In",
    category: category,
    icon: zoomInIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "PageDown",
    onKeyEvent: () => {
      getServers().getServer(server_id).zoom_out(stream_id);
    },
    description: "Zoom Out",
    category: category,
    icon: zoomOutIcon,
    dependencies: [stream_id, server_id],
  });

  useKeyPress({
    key: "Backspace",
    onKeyEvent: () => {
      getServers().getServer(server_id).setZoomFactor(stream_id, 1);
    },
    description: "Set Zoom to 1:1",
    category: category,
    icon: setZoom1_1Icon,
    dependencies: [stream_id, server_id],
  })

  useKeyPress({
    key: "Numpad1",
    onKeyEvent: () => {
      getServers().getServer(server_id).resetZoomCenter(stream_id);
    },
    description: "Reset Zoom Center",
    category: category,
    icon: resetZoomCenterIcon,
    dependencies: [stream_id, server_id],
  })

  //TODO implement a key binding "fix full size" that sets a parameter on the server that makes the zoom factor always be set to a value where the whole image is visible
  //implement this on the server side

  useKeyPress({
    key: "F",
    onKeyEvent: () => {
      getServers().getServer(server_id).setStreamParameters(stream_id, { fix_full_size: true });
    },
    description: "Display the whole image",
    category: category,
    icon: resetZoomIconFull,
    dependencies: [stream_id, server_id],
  })
}

