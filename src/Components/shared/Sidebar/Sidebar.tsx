import React, { createContext, useContext, useState } from "react";
import { Offcanvas } from "react-bootstrap";
import { NavLink, useLocation } from "react-router-dom";
import {
  Menu,
  Video,
  PlayCircle,
  Server,
  Settings,
  Home,
  HelpCircle,
} from "lucide-react";
import "./sidebar.css";

interface SidebarContextType {
  show: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType>({
  show: false,
  openSidebar: () => {},
  closeSidebar: () => {},
  toggleSidebar: () => {},
});

export function useSidebar() {
  return useContext(SidebarContext);
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  const location = useLocation();
  const pathname = location.pathname;

  const openSidebar = React.useCallback(() => {
    setShow(true);
  }, []);

  const closeSidebar = React.useCallback(() => {
    setShow(false);
  }, []);

  const toggleSidebar = React.useCallback(() => {
    setShow((prev) => !prev);
  }, []);

  // Auto-close sidebar whenever route/pathname changes
  React.useEffect(() => {
    setShow(false);
  }, [pathname]);

  return (
    <SidebarContext.Provider
      value={{ show, openSidebar, closeSidebar, toggleSidebar }}
    >
      {children}

      {/* Offcanvas Drawer for Navigation */}
      <Offcanvas
        show={show}
        onHide={closeSidebar}
        className="vci-sidebar-offcanvas"
        placement="start"
        restoreFocus={false}
        enforceFocus={false}
      >
        <Offcanvas.Header closeButton className="vci-sidebar-header">
          <Offcanvas.Title className="vci-sidebar-title">
            VCI WebApp
          </Offcanvas.Title>
        </Offcanvas.Header>

        <Offcanvas.Body className="vci-sidebar-body">
          <nav className="vci-sidebar-nav">
            <NavLink
              to="/preview"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              <Video size={18} />
              <span>Preview</span>
            </NavLink>

            <NavLink
              to="/vci-automation"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              <PlayCircle size={18} />
              <span>VCI Automation</span>
            </NavLink>

            <NavLink
              to="/servers"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              <Server size={18} />
              <span>Server Status</span>
            </NavLink>

            <NavLink
              to="/config"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              <Settings size={18} />
              <span>Settings</span>
            </NavLink>

            <NavLink
              to="/"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
              end
            >
              <Home size={18} />
              <span>System Dashboard</span>
            </NavLink>
          </nav>
        </Offcanvas.Body>
      </Offcanvas>
    </SidebarContext.Provider>
  );
}

export function AppSidebar() {
  const { openSidebar } = useSidebar();
  const location = useLocation();
  const pathname = location.pathname;

  const isDashboardActive = pathname === "/";
  const isPreviewActive = pathname.startsWith("/preview");
  const isAutomationActive = pathname.startsWith("/vci-automation");
  const isServerActive = pathname.startsWith("/servers") || pathname.startsWith("/videostream");
  const isConfigActive = pathname.startsWith("/config");

  return (
    <aside className="vci-app-sidebar">
      <div className="vci-app-sidebar-top">
        {/* Hamburger Drawer Button */}
        <button
          className="vci-sidebar-icon-btn"
          onClick={openSidebar}
          title="Open Navigation Menu"
          type="button"
        >
          <Menu size={20} />
        </button>

        {/* 1. Preview & Spatial Map */}
        <NavLink
          to="/preview"
          className={`vci-sidebar-icon-btn ${isPreviewActive ? "active" : ""}`}
          title="Preview & Spatial Map"
        >
          {isPreviewActive && <span className="active-indicator" />}
          <Video size={19} />
        </NavLink>

        {/* 2. VCI Automation */}
        <NavLink
          to="/vci-automation"
          className={`vci-sidebar-icon-btn ${isAutomationActive ? "active" : ""}`}
          title="VCI Automation"
        >
          {isAutomationActive && <span className="active-indicator" />}
          <PlayCircle size={19} />
        </NavLink>

        {/* 3. Server Status */}
        <NavLink
          to="/servers"
          className={`vci-sidebar-icon-btn ${isServerActive ? "active" : ""}`}
          title="Server Status"
        >
          {isServerActive && <span className="active-indicator" />}
          <Server size={19} />
        </NavLink>

        {/* 4. Settings */}
        <NavLink
          to="/config"
          className={`vci-sidebar-icon-btn ${isConfigActive ? "active" : ""}`}
          title="Settings"
        >
          {isConfigActive && <span className="active-indicator" />}
          <Settings size={19} />
        </NavLink>

        {/* 5. Dashboard */}
        <NavLink
          to="/"
          className={`vci-sidebar-icon-btn ${isDashboardActive ? "active" : ""}`}
          title="Dashboard"
          end
        >
          {isDashboardActive && <span className="active-indicator" />}
          <Home size={19} />
        </NavLink>
      </div>
    </aside>
  );
}

export function MobileSegmentedNavStrip() {
  const location = useLocation();
  const pathname = location.pathname;

  const isDashboardActive = pathname === "/";
  const isPreviewActive = pathname.startsWith("/preview");
  const isAutomationActive = pathname.startsWith("/vci-automation");
  const isServerActive = pathname.startsWith("/servers") || pathname.startsWith("/videostream");
  const isConfigActive = pathname.startsWith("/config");

  return (
    <nav className="vci-mobile-segmented-nav">
      <div className="vci-mobile-nav-scroll-container">
        <NavLink
          to="/"
          className={`vci-mobile-nav-pill ${isDashboardActive ? "active" : ""}`}
          end
        >
          <Home size={14} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/preview"
          className={`vci-mobile-nav-pill ${isPreviewActive ? "active" : ""}`}
        >
          <Video size={14} />
          <span>Preview &amp; Spatial Map</span>
        </NavLink>

        <NavLink
          to="/vci-automation"
          className={`vci-mobile-nav-pill ${isAutomationActive ? "active" : ""}`}
        >
          <PlayCircle size={14} />
          <span>Automation</span>
        </NavLink>

        <NavLink
          to="/servers"
          className={`vci-mobile-nav-pill ${isServerActive ? "active" : ""}`}
        >
          <Server size={14} />
          <span>Servers</span>
        </NavLink>

        <NavLink
          to="/config"
          className={`vci-mobile-nav-pill ${isConfigActive ? "active" : ""}`}
        >
          <Settings size={14} />
          <span>Settings</span>
        </NavLink>
      </div>
    </nav>
  );
}

export function Sidebar() {
  return (
    <>
      <MobileSegmentedNavStrip />
      <AppSidebar />
    </>
  );
}
