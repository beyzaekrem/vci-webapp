import React, { createContext, useContext, useState } from "react";
import { Offcanvas } from "react-bootstrap";
import { NavLink, useLocation } from "react-router-dom";
import {
  Menu,
  Video,
  PlayCircle,
  Grid,
  Sliders,
  Server,
  Settings,
  Info,
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

  const openSidebar = () => setShow(true);
  const closeSidebar = () => setShow(false);
  const toggleSidebar = () => setShow((prev) => !prev);

  const handleHelpClick = () => {
    closeSidebar();
    const event = new KeyboardEvent("keydown", { key: "h", bubbles: true });
    window.dispatchEvent(event);
  };

  return (
    <SidebarContext.Provider
      value={{ show, openSidebar, closeSidebar, toggleSidebar }}
    >
      {children}
      <Offcanvas
        show={show}
        onHide={closeSidebar}
        className="vci-sidebar-offcanvas"
        placement="start"
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
              Preview
            </NavLink>

            <NavLink
              to="/vci-automation"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              VCI Automation
            </NavLink>

            <NavLink
              to="/capture"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              Capture
            </NavLink>

            <NavLink
              to="/calibrate"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              Calibrate
            </NavLink>

            <NavLink
              to="/servers"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              Server Status
            </NavLink>

            <NavLink
              to="/config"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              Settings
            </NavLink>

            <NavLink
              to="/about"
              className={({ isActive }) =>
                `vci-sidebar-link ${isActive ? "active" : ""}`
              }
              onClick={closeSidebar}
            >
              About
            </NavLink>

            <div className="vci-sidebar-divider" />

            <button
              type="button"
              className="vci-sidebar-help-btn"
              onClick={handleHelpClick}
            >
              Help &amp; Documentation
            </button>
          </nav>
        </Offcanvas.Body>
      </Offcanvas>
    </SidebarContext.Provider>
  );
}

/**
 * Vertical Icon Rail (Closed Sidebar state) rendered on all pages
 * Top-to-bottom sequence matching user screenshot:
 * 1. Preview
 * 2. VCI Automation
 * 3. Capture
 * 4. Calibrate
 * 5. Server Status
 * 6. Settings
 * 7. About
 */
export function AppSidebar() {
  const { openSidebar } = useSidebar();
  const location = useLocation();
  const pathname = location.pathname;

  const isPreviewActive = pathname === "/" || pathname.startsWith("/preview");
  const isAutomationActive = pathname.startsWith("/vci-automation");
  const isCaptureActive = pathname.startsWith("/capture");
  const isCalibrateActive = pathname.startsWith("/calibrate");
  const isServerActive = pathname.startsWith("/servers") || pathname.startsWith("/videostream");
  const isConfigActive = pathname.startsWith("/config");
  const isAboutActive = pathname.startsWith("/about");

  const handleHelpClick = () => {
    const event = new KeyboardEvent("keydown", { key: "h", bubbles: true });
    window.dispatchEvent(event);
  };

  return (
    <aside className="vci-app-sidebar">
      <div className="vci-app-sidebar-top">
        {/* Hamburger Menu Toggle Button */}
        <button
          className="vci-sidebar-icon-btn"
          onClick={openSidebar}
          title="Open Navigation Menu"
          type="button"
        >
          <Menu size={20} />
        </button>

        {/* 1. Preview Streams */}
        <NavLink
          to="/preview"
          className={`vci-sidebar-icon-btn ${isPreviewActive ? "active" : ""}`}
          title="Preview"
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

        {/* 3. Capture */}
        <NavLink
          to="/capture"
          className={`vci-sidebar-icon-btn ${isCaptureActive ? "active" : ""}`}
          title="Capture"
        >
          {isCaptureActive && <span className="active-indicator" />}
          <Grid size={19} />
        </NavLink>

        {/* 4. Calibrate */}
        <NavLink
          to="/calibrate"
          className={`vci-sidebar-icon-btn ${isCalibrateActive ? "active" : ""}`}
          title="Calibrate"
        >
          {isCalibrateActive && <span className="active-indicator" />}
          <Sliders size={19} />
        </NavLink>

        {/* 5. Server Status */}
        <NavLink
          to="/servers"
          className={`vci-sidebar-icon-btn ${isServerActive ? "active" : ""}`}
          title="Server Status"
        >
          {isServerActive && <span className="active-indicator" />}
          <Server size={19} />
        </NavLink>

        {/* 6. Settings */}
        <NavLink
          to="/config"
          className={`vci-sidebar-icon-btn ${isConfigActive ? "active" : ""}`}
          title="Settings"
        >
          {isConfigActive && <span className="active-indicator" />}
          <Settings size={19} />
        </NavLink>

        {/* 7. About */}
        <NavLink
          to="/about"
          className={`vci-sidebar-icon-btn ${isAboutActive ? "active" : ""}`}
          title="About"
        >
          {isAboutActive && <span className="active-indicator" />}
          <Info size={19} />
        </NavLink>
      </div>

      <div className="vci-app-sidebar-bottom">
        <button
          className="vci-sidebar-icon-btn"
          title="Help & Documentation (Press h)"
          onClick={handleHelpClick}
          type="button"
        >
          <HelpCircle size={19} />
        </button>
      </div>
    </aside>
  );
}

export function Sidebar() {
  return <AppSidebar />;
}
