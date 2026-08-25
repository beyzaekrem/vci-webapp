import { createContext, useContext, useState } from "react";
import { Toast, ToastContainer } from "react-bootstrap";
import { ReactNode } from "react";

const MAX_NOTIFICATIONS = 3;

export function Notifications() {
  const { notifications, removeNotification } = useNotificationContext();

  return (
    <ToastContainer style={{ position: "fixed", right: 30, bottom: 30, zIndex: 9999 }}>
      {notifications.map((el, ind) => {
        return (
          <Toast
            key={el.id}
            autohide
            delay={8000}
            onClose={() => {
              removeNotification(ind);
            }}
          >
            <Toast.Header>
              <strong className="me-auto">{el.title}</strong>
              <small className="text-muted">{el.time}</small>
            </Toast.Header>
            <Toast.Body>{el.body}</Toast.Body>
          </Toast>
        );
      })}
    </ToastContainer>
  );
}

export function WithNotifications({ children }: { children: ReactNode }) {
  return (
    <WithNotificationContext>
      {children}
      <Notifications />
    </WithNotificationContext>
  );
}

interface Notification {
  title: any;
  body: any;
  time: string;
  id: number;
}

//Notifications
const NotificationContext = createContext({
  notifications: new Array<Notification>(),
  removeNotification: (i: number) => { },
  addNotification: (title: any, body: any) => { },
});
export function useNotificationContext() {
  return useContext(NotificationContext);
}

export function WithNotificationContext({ children }: { children: ReactNode }) {
  const { notifications, addNotification, removeNotification } =
    useNotifications();

  return (
    <NotificationContext.Provider
      value={{ notifications, addNotification, removeNotification }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

function useNotifications() {
  const [notifications, setNotifications] = useState(new Array<Notification>());
  const [count, setCount] = useState(0);

  function addNotification(title: any, body: any) {
    const nNo = [...notifications];
    var time = new Date().toLocaleTimeString();
    nNo.push({ title: title, body: body, time: time, id: count });
    // Keep only the most recent notifications
    while (nNo.length > MAX_NOTIFICATIONS) {
      nNo.shift();
    }
    setNotifications(nNo);
    setCount(count + 1);
  }

  function removeNotification(ind: number) {
    const nNo = [...notifications];
    nNo.splice(ind, 1);
    console.log(nNo);
    setNotifications(nNo);
  }

  return { notifications, addNotification, removeNotification };
}
