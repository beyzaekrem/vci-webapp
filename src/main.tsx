import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import "./scss/custom.scss";

import { RouterProvider } from "react-router-dom";
import { WithKeyBindingContext } from "./Utility/KeyBindings";

import { router } from "./router.tsx";
import { initControlServer } from "./network/control-server";
import { initCaptureServers } from "./network/capture-server";
import { initVCI } from "./network/vci-automation";

const container = document.getElementById("root");
if(!container) {
  throw new Error("Root container missing in index.html");
}

// Initialize singleton instances for control server and capture servers with default configurations.

initControlServer({
  defaultConfig: {
    address: "127.0.0.1",
  },
  nameInStorage: "controlServerConfig",
});
initCaptureServers({
  defaultConfig: {
    addresses: [
      "127.0.0.1",
    ],
  },
  nameInStorage: "captureServerConfig",
});

initVCI({
  defaultConfig: {
    address: "127.0.0.1",
    port: 2525,
  },
  nameInStorage: "vciAutomationConfig",
});

const root = ReactDOM.createRoot(container);

root.render(
  <React.StrictMode>
    <div className="App">
      <header className="App-header" />
      <WithKeyBindingContext>
        <RouterProvider router={router} />
      </WithKeyBindingContext>
    </div>
  </React.StrictMode>,
);
