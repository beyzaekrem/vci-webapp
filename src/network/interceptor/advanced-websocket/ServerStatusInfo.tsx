import { Badge, Spinner } from "react-bootstrap";
import { InfoPopUp } from "../../../Utility/UI";
import { ReadyState, useConnectionStatus } from "./ConnectionStatus";
import { WebsocketConnection } from "./WebsocketConnection";

const statusMessages = {
  online: {
    msg: "Online",
    bg: "success",
    txt: "Server is online",
  },
  offline: {
    msg: "Offline",
    bg: "danger",
    txt: "Server is offline",
  },
  load: {
    msg: "Requesting status...",
    bg: "secondary",
    txt: "Requesting server status...",
  },
  error: {
    msg: "Error",
    bg: "danger",
    txt: "There was an error requesting the server's status. Check the browser console.",
  },
};

type StatusKey = keyof typeof statusMessages;

function getConnectionStatusInfo(state: number): StatusKey {
  if(state === ReadyState.OPEN) return "online";
  if(state === ReadyState.CLOSED) return "offline";
  return "load";
}

export function ServerStatusInfo({
  socket,
}: {
  socket: WebsocketConnection<any, any>;
}) {
  const state = useConnectionStatus(socket);
  const status = getConnectionStatusInfo(state);

  return (
    <InfoPopUp
      title={statusMessages[status].msg}
      longTitle={statusMessages[status].msg}
      content={statusMessages[status].txt}
    >
      <Badge
        className="btn-primary"
        pill
        bg={statusMessages[status].bg}
        onClick={() => {
          console.log("waa");
        }}
      >
        {status === "load" ? (
          <Spinner
            animation="border"
            role="status"
            size="sm"
            style={{ height: "12px", width: "12px" }}
          >
            <span className="visually-hidden">Loading...</span>
          </Spinner>
        ) : (
          statusMessages[status].msg
        )}
      </Badge>
    </InfoPopUp>
  );
}
