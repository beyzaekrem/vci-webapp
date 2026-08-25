/**
 * @packageDocumentation
 *
 * Central router configuration for the application.
 */
import { createHashRouter, Outlet, Navigate } from "react-router-dom";

import {
  Dashboard,
  CombinedPage,
  ConfigPage,
  StartPage,
  VCIAutomationPage,
  JsonFormsTestPage,
  ScriptOutputPage,
} from "./pages";

import { WithNotifications } from "./Utility/Notifications";
import { SidebarProvider, AppSidebar } from "./Components/shared/Sidebar/Sidebar.tsx";
import { LocalStorageProvider } from "./Utility/Storage";
import { GridFromQueryParam } from "./Components/Videostream/WebsocketGrid.tsx";
import { StreamsPerServer } from "./Components/Videostream/StreamsPerServer.tsx";

function WithSidebarLayout() {
  return (
    <LocalStorageProvider>
      <SidebarProvider>
        <div className="vci-app-layout">
          <AppSidebar />
          <main className="vci-app-main-content">
            <WithNotifications>
              <Outlet />
            </WithNotifications>
          </main>
        </div>
      </SidebarProvider>
    </LocalStorageProvider>
  );
}

/**
 * Defines the application's routes, associating each url/ path with a specific page.
 * Routes are nested under a single layout so every page gets sidebar and notifications.
 */
export const router = createHashRouter([
  {
    path: "/",
    element: <WithSidebarLayout />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: "config",
        element: <ConfigPage />,
      },
      {
        path: "servers",
        element: <StartPage />,
      },
      {
        path: "videostream",
        element: <GridFromQueryParam />,
      },
      {
        path: "videostream/server/:serverId",
        element: <StreamsPerServer />,
      },
      {
        path: "preview",
        element: <CombinedPage />,
      },
      {
        path: "calibrate",
        element: <Navigate to="/preview" replace />,
      },

      {
        path: "vci-automation",
        element: <VCIAutomationPage />,
      },
      {
        path: "vci-automation/script_output/:runnerId",
        element: <ScriptOutputPage />,
      },
      {
        path: "jsonforms-test",
        element: <JsonFormsTestPage />,
      }
    ],
  },
]);
