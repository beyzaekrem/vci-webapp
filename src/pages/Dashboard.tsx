import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Video,
  PlayCircle,
  Sliders,
  Server,
  Settings,
  Keyboard,
  Camera,
  Activity,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { ServerStatusButton } from "../Components/shared/ServerStatusModal";
import { NoAutomaticRefreshes } from "../Components/shared/WarningPopups.tsx";
import { getServers, useCameraIndices } from "../network/capture-server";
import "./Dashboard.css";

const modules = [
  {
    title: "Preview Streams",
    desc: "Interactive spatial camera map and real-time video stream inspection",
    icon: Video,
    path: "/preview",
    badge: "Live View",
  },
  {
    title: "VCI Automation",
    desc: "Configure, execute, and monitor background automation scripts",
    icon: PlayCircle,
    path: "/vci-automation",
    badge: "Automation",
  },
  {
    title: "Camera Calibration",
    desc: "Exposure adjustment and dual-view integer zoom calibration tool",
    icon: Sliders,
    path: "/calibrate",
    badge: "Calibration",
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
  const navigate = useNavigate();
  const cameraIndices = useCameraIndices();

  const stats = useMemo(() => {
    const servers = getServers();
    const serverCount = servers.servers.length;
    const cameraCount = cameraIndices.length;
    return { serverCount, cameraCount };
  }, [cameraIndices]);

  return (
    <div className="ps-content-wrapper">
      {/* Header Bar */}
      <header className="ps-header-bar">
        <h1 className="ps-header-title">System Dashboard</h1>
        <ServerStatusButton />
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
                Centralized control panel to configure, stream, calibrate, and automate multi-camera capture servers within the VCI environment.
              </p>
            </div>
            <div className="dash-system-status-chip">
              <span className="dash-status-dot" />
              <span>System Operational</span>
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

          {/* Core Modules Grid */}
          <section className="dash-section">
            <div className="dash-section-header">
              <h3 className="dash-section-title">Application Modules</h3>
            </div>
            <div className="dash-modules-grid">
              {modules.map((mod) => (
                <div
                  key={mod.path}
                  className="dash-module-card"
                  onClick={() => navigate(mod.path)}
                >
                  <div className="dash-module-header">
                    <div className="dash-module-icon">
                      <mod.icon size={20} />
                    </div>
                    <span className="dash-module-badge">{mod.badge}</span>
                  </div>
                  <h4 className="dash-module-title">{mod.title}</h4>
                  <p className="dash-module-desc">{mod.desc}</p>
                  <div className="dash-module-footer">
                    <span>Open Module</span>
                    <ArrowRight size={14} className="dash-arrow-icon" />
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* System Overview & Capabilities Section */}
          <section className="dash-section">
            <div className="dash-section-header">
              <h3 className="dash-section-title">About VCI WebApp Architecture</h3>
            </div>
            <div className="dash-overview-card">
              <p className="dash-overview-intro">
                The <strong>VCI WebApp</strong> sits at the highest abstraction layer of the VCI multi-camera capture infrastructure. It provides a centralized Web GUI to monitor, stream, calibrate, and automate multi-node video acquisition servers in real time.
              </p>
              <div className="dash-features-grid">
                <div className="dash-feature-item">
                  <div className="dash-feature-dot" />
                  <div>
                    <strong className="dash-feature-title">Real-Time Multi-Camera Streaming</strong>
                    <p className="dash-feature-desc">Visualize low-latency H.264 video streams from individual cameras or multi-node server grids via WebSocket connections.</p>
                  </div>
                </div>
                <div className="dash-feature-item">
                  <div className="dash-feature-dot" />
                  <div>
                    <strong className="dash-feature-title">2D Spatial Layout Mapping</strong>
                    <p className="dash-feature-desc">Interactive stage map mapping physical pillar locations (P1–P8) and slot heights for instant camera identification and selection.</p>
                  </div>
                </div>
                <div className="dash-feature-item">
                  <div className="dash-feature-dot" />
                  <div>
                    <strong className="dash-feature-title">Remote Script Automation</strong>
                    <p className="dash-feature-desc">Configure, launch, and monitor remote Python automation scripts and background capture pipelines through the VCI Automation API.</p>
                  </div>
                </div>
                <div className="dash-feature-item">
                  <div className="dash-feature-dot" />
                  <div>
                    <strong className="dash-feature-title">Calibration & Parameter Tuning</strong>
                    <p className="dash-feature-desc">Live exposure control, trigger source switching, and dual-view integer zoom tools for precise hardware calibration.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Technical Info & Documentation Row */}
          <div className="dash-bottom-grid">
            <div className="dash-sub-card">
              <div className="dash-sub-header">
                <Keyboard size={18} className="dash-sub-icon" />
                <h4 className="dash-sub-title">Navigation & Keyboard Shortcuts</h4>
              </div>
              <p className="dash-sub-text">
                Press <kbd>h</kbd> anywhere in the application to display context-sensitive keybindings and documentation. Hovering over buttons reveals shortcut bindings in square brackets <strong>[]</strong>.
              </p>
            </div>

            <div className="dash-sub-card">
              <div className="dash-sub-header">
                <ShieldCheck size={18} className="dash-sub-icon" />
                <h4 className="dash-sub-title">System Status & Data Refresh</h4>
              </div>
              <NoAutomaticRefreshes />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
