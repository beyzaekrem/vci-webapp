import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Video,
  PlayCircle,
  Server,
  Settings,
  Keyboard,
  Camera,
  Activity,
  ArrowRight,
  ShieldCheck,
  Menu,
  Sun,
  Moon,
} from "lucide-react";
import { ServerStatusButton, HelpButton } from "../Components/shared/ServerStatusModal";
import { useSidebar } from "../Components/shared/Sidebar/Sidebar";
import { NoAutomaticRefreshes } from "../Components/shared/WarningPopups.tsx";
import { getServers, useCameraIndices } from "../network/capture-server";
import { useTheme } from "../Utility/Theme/ThemeContext";
import "./Dashboard.css";

const modules = [
  {
    title: "Preview & Spatial Map",
    desc: "Interactive 2D/3D spatial camera map and real-time video stream inspection",
    icon: Video,
    path: "/preview",
    badge: "Unified View",
  },
  {
    title: "VCI Automation",
    desc: "Configure, execute, and monitor background automation scripts",
    icon: PlayCircle,
    path: "/vci-automation",
    badge: "Automation",
  },
  {
    title: "Server Status",
    desc: "Control server and capture server health, logs, and connection state",
    icon: Server,
    path: "/servers",
    badge: "Network",
  },
  {
    title: "System Settings",
    desc: "Network endpoints, default addresses, and persistent storage config",
    icon: Settings,
    path: "/config",
    badge: "Config",
  },
];

export function Dashboard() {
  const { openSidebar } = useSidebar();
  const navigate = useNavigate();
  const cameraIndices = useCameraIndices();
  const { theme, toggleTheme } = useTheme();

  const stats = useMemo(() => {
    const servers = getServers();
    const serverCount = servers.servers.length;
    const cameraCount = cameraIndices.length;
    return { serverCount, cameraCount };
  }, [cameraIndices]);

  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar vci-unified-header">
        <div className="vci-header-left">
          <button
            type="button"
            className="vci-header-hamburger-btn"
            onClick={openSidebar}
            title="Open Navigation Menu"
          >
            <Menu size={18} />
          </button>
          <h1 className="vci-header-title">System Dashboard</h1>
        </div>
        <div className="vci-header-right">
          <HelpButton />
          <ServerStatusButton />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="dash-main">
        <div className="dash-container">
          {/* Welcome Banner */}
          <div className="dash-welcome-card">
            <div className="dash-welcome-left">
              <div className="dash-title-row">
                <h2 className="dash-welcome-title">VCI WebApp System Overview</h2>
                <span className="dash-ver-badge">v1.0.0</span>
              </div>
              <p className="dash-welcome-desc">
                Centralized control panel to configure, stream, and automate multi-camera capture servers within the VCI environment.
              </p>
            </div>
            <div className="dash-system-status-chip">
              <span className="dash-status-dot" />
              <span>System Operational</span>
            </div>
          </div>

          {/* Theme Toggle Card */}
          <div className="vci-theme-card">
            <div className="vci-theme-card-left">
              <div className="vci-theme-card-icon">
                {theme === "dark" ? <Moon size={20} /> : <Sun size={20} />}
              </div>
              <div>
                <p className="vci-theme-card-title">
                  {theme === "dark" ? "Dark Mode" : "Light Mode"}
                </p>
                <p className="vci-theme-card-desc">
                  Switch between dark and light interface appearance
                </p>
              </div>
            </div>
            <div className="vci-theme-toggle">
              <span className="vci-theme-toggle-label">
                {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
              </span>
              <label
                className="vci-theme-switch"
                title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
                aria-label="Toggle dark/light mode"
              >
                <input
                  type="checkbox"
                  checked={theme === "dark"}
                  onChange={toggleTheme}
                  id="theme-toggle-checkbox"
                />
                <span className="vci-theme-switch-track">
                  <span className="vci-theme-switch-thumb">
                    {theme === "dark" ? "🌙" : "☀️"}
                  </span>
                </span>
              </label>
            </div>
          </div>

          {/* Key Metrics Row */}
          <div className="dash-metrics-grid">
            <div className="dash-metric-card">
              <div className="dash-metric-icon-box">
                <Server size={20} />
              </div>
              <div className="dash-metric-data">
                <span className="dash-metric-value">{stats.serverCount}</span>
                <span className="dash-metric-label">Capture Servers</span>
              </div>
            </div>

            <div className="dash-metric-card">
              <div className="dash-metric-icon-box">
                <Camera size={20} />
              </div>
              <div className="dash-metric-data">
                <span className="dash-metric-value">{stats.cameraCount}</span>
                <span className="dash-metric-label">Registered Cameras</span>
              </div>
            </div>

            <div className="dash-metric-card">
              <div className="dash-metric-icon-box">
                <Activity size={20} />
              </div>
              <div className="dash-metric-data">
                <span className="dash-metric-value">Active</span>
                <span className="dash-metric-label">Control Protocol</span>
              </div>
            </div>
          </div>

          {/* Detailed System Capabilities & Page Guide */}
          <section className="dash-section">
            <div className="dash-section-header">
              <h3 className="dash-section-title">System Capabilities & Page Guide</h3>
            </div>
            <div className="dash-guide-grid">
              {/* Preview & Spatial Map */}
              <div className="dash-guide-card" onClick={() => navigate("/preview")}>
                <div className="dash-guide-card-header">
                  <div className="dash-guide-icon-box">
                    <Video size={20} />
                  </div>
                  <div>
                    <h4 className="dash-guide-card-title">Preview &amp; Spatial Map</h4>
                    <span className="dash-guide-card-path">/preview</span>
                  </div>
                </div>
                <p className="dash-guide-card-intro">
                  Real-time multi-camera inspection and spatial stage mapping view.
                </p>
                <ul className="dash-guide-list">
                  <li><strong>2D Stage Spatial Map:</strong> Interactive layout mapping physical pillar locations (P1–P8) and slot heights.</li>
                  <li><strong>Live Stream Inspection:</strong> Real-time H.264 video streams from individual or multi-node camera grids.</li>
                  <li><strong>Server &amp; Node Filtering:</strong> Filter cameras by server node (10.3.10.x), pillar, or shorthand IDs.</li>
                </ul>
                <div className="dash-guide-footer">
                  <span>Navigate to Preview</span>
                  <ArrowRight size={14} />
                </div>
              </div>

              {/* VCI Automation */}
              <div className="dash-guide-card" onClick={() => navigate("/vci-automation")}>
                <div className="dash-guide-card-header">
                  <div className="dash-guide-icon-box">
                    <PlayCircle size={20} />
                  </div>
                  <div>
                    <h4 className="dash-guide-card-title">VCI Automation</h4>
                    <span className="dash-guide-card-path">/vci-automation</span>
                  </div>
                </div>
                <p className="dash-guide-card-intro">
                  Configure, execute, and monitor remote background Python automation scripts.
                </p>
                <ul className="dash-guide-list">
                  <li><strong>Active Script Selection:</strong> Select image acquisition, background capture, or calibration pipelines.</li>
                  <li><strong>Script Form &amp; Validation:</strong> Configure required (*) exposure, gain, and target server parameters.</li>
                  <li><strong>Live Execution Logs:</strong> Real-time terminal output streaming with full-screen log inspector.</li>
                </ul>
                <div className="dash-guide-footer">
                  <span>Navigate to Automation</span>
                  <ArrowRight size={14} />
                </div>
              </div>

              {/* Server Status */}
              <div className="dash-guide-card" onClick={() => navigate("/servers")}>
                <div className="dash-guide-card-header">
                  <div className="dash-guide-icon-box">
                    <Server size={20} />
                  </div>
                  <div>
                    <h4 className="dash-guide-card-title">Server Status</h4>
                    <span className="dash-guide-card-path">/servers</span>
                  </div>
                </div>
                <p className="dash-guide-card-intro">
                  Centralized health, connection status, and camera node discovery dashboard.
                </p>
                <ul className="dash-guide-list">
                  <li><strong>Connection Monitoring:</strong> Real-time WebSocket connection state (Online / Connecting / Offline).</li>
                  <li><strong>Control &amp; Capture Nodes:</strong> Direct inspection of Control Server and Capture Nodes (10.3.10.1–15).</li>
                  <li><strong>Camera Discovery:</strong> Auto-detection of connected hardware camera devices across nodes.</li>
                </ul>
                <div className="dash-guide-footer">
                  <span>Navigate to Server Status</span>
                  <ArrowRight size={14} />
                </div>
              </div>

              {/* Settings / Config */}
              <div className="dash-guide-card" onClick={() => navigate("/config")}>
                <div className="dash-guide-card-header">
                  <div className="dash-guide-icon-box">
                    <Settings size={20} />
                  </div>
                  <div>
                    <h4 className="dash-guide-card-title">System Settings</h4>
                    <span className="dash-guide-card-path">/config</span>
                  </div>
                </div>
                <p className="dash-guide-card-intro">
                  Network endpoint configuration, environment presets, and system parameters.
                </p>
                <ul className="dash-guide-list">
                  <li><strong>Quick Presets:</strong> One-click instant switch between Simulated (127.0.0.1) and Real Rig (10.3.10.x).</li>
                  <li><strong>Control &amp; VCI Endpoints:</strong> Update Control Server and VCI Automation IP addresses, ports, and routes.</li>
                  <li><strong>Capture Nodes List:</strong> Batch configure capture server IP address lists and WebSocket routes.</li>
                </ul>
                <div className="dash-guide-footer">
                  <span>Navigate to Settings</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            </div>
          </section>

          {/* Important Guidelines & Operational Best Practices */}
          <section className="dash-section">
            <div className="dash-section-header">
              <h3 className="dash-section-title">Important Guidelines &amp; Operational Best Practices</h3>
            </div>
            <div className="dash-guidelines-card">
              <div className="dash-guidelines-grid">
                {/* 1. Environment Switching */}
                <div className="dash-guideline-item">
                  <div className="dash-guideline-badge">01. Environment Presets</div>
                  <h4 className="dash-guideline-title">Simulated Mode vs. Real Production Rig</h4>
                  <p className="dash-guideline-desc">
                    When testing locally without hardware, use <strong>Simulated Mode (127.0.0.1)</strong>. When connecting to the physical setup, switch to <strong>Real Production Rig (10.3.10.x)</strong> in <kbd>Settings</kbd>. Ensure your workstation is connected to the <code>10.3.10.0/24</code> local subnet.
                  </p>
                </div>

                {/* 2. Mandatory Fields */}
                <div className="dash-guideline-item">
                  <div className="dash-guideline-badge">02. Script Automation</div>
                  <h4 className="dash-guideline-title">Mandatory Script Parameters</h4>
                  <p className="dash-guideline-desc">
                    In <strong>VCI Automation</strong>, fields marked with a red asterisk <strong>*</strong> are required for script execution. Ensure exposure times, gain levels, and target node IPs are filled before clicking <em>Execute Script</em>.
                  </p>
                </div>

                {/* 3. Port & Websocket Connection */}
                <div className="dash-guideline-item">
                  <div className="dash-guideline-badge">03. Network Endpoints</div>
                  <h4 className="dash-guideline-title">Port &amp; Connection Status</h4>
                  <p className="dash-guideline-desc">
                    Default ports: Control Server (<code>2443</code>), VCI Automation API (<code>2525</code>), Capture Nodes (<code>2443</code>). Check the top-right <strong>Connection Status</strong> button to verify live WebSocket links.
                  </p>
                </div>

                {/* 4. Keyboard Shortcuts */}
                <div className="dash-guideline-item">
                  <div className="dash-guideline-badge">04. Quick Navigation</div>
                  <h4 className="dash-guideline-title">Shortcuts &amp; Live Logs</h4>
                  <p className="dash-guideline-desc">
                    Press <kbd>h</kbd> anywhere to open context-sensitive shortcuts. Use the <em>Fullscreen Logs</em> button in VCI Automation to open a dedicated terminal log window.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Technical Info & Documentation Row */}
          <div className="dash-bottom-grid">
            <div className="dash-sub-card">
              <div className="dash-sub-header">
                <Keyboard size={18} className="dash-sub-icon" />
                <h4 className="dash-sub-title">Navigation &amp; Keyboard Shortcuts</h4>
              </div>
              <p className="dash-sub-text">
                Press <kbd>h</kbd> anywhere in the application to display context-sensitive keybindings and documentation. Hovering over buttons reveals shortcut bindings in square brackets <strong>[]</strong>.
              </p>
            </div>

            <div className="dash-sub-card">
              <div className="dash-sub-header">
                <ShieldCheck size={18} className="dash-sub-icon" />
                <h4 className="dash-sub-title">System Status &amp; Data Refresh</h4>
              </div>
              <NoAutomaticRefreshes />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
