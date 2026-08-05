import { useRef, useState, useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { getServers } from "../../network/capture-server";
import { usePerformanceData, DisplayPerformanceData, getCurrentTime } from "./usePerformanceData";

export interface StreamProps {
    serverIndex: number;
    cameraIndex: number;
    width: number;
    height: number;
    onStreamID?: (id: string) => void;
    constantStreamID: string | null;
    autoStart?: boolean;
}

export function StreamWebsocket({
    serverIndex, cameraIndex, width, height, onStreamID, constantStreamID, autoStart = true
}: StreamProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const idOfRunningStream = useRef<string | null>(null);
    const [isConnecting, setIsConnecting] = useState(true);
    const [hasError, setHasError] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const { performanceData, measure } = usePerformanceData();
    const lastFrameTimeRef = useRef<number>(Date.now());
    const hasReceivedFirstFrameRef = useRef<boolean>(false);

    useEffect(() => {
        // 1. Immediately wipe canvas to prevent showing stale frames from previous cameras
        if (canvasRef.current) {
            const ctx = canvasRef.current.getContext("2d");
            if (ctx) {
                ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
            }
        }

        // 2. Reset states for the new camera selection
        setIsConnecting(true);
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;

        if (!constantStreamID) {
            return;
        }

        idOfRunningStream.current = constantStreamID;
        let stopped = false;

        const startTime = Date.now();
        const initialGracePeriodMs = 12000; // 12s grace period for socket connect + mode switch + first frame
        const frameTimeoutMs = 6000; // 6s timeout between subsequent frames

        // 3. Timeout check: flag as offline only if grace period / frame interval is exceeded
        const timeoutTimer = setInterval(() => {
            if (stopped) return;
            const now = Date.now();
            if (!hasReceivedFirstFrameRef.current) {
                if (now - startTime > initialGracePeriodMs) {
                    setIsConnecting(false);
                    setHasError(true);
                    setErrorMessage("Unable to retrieve video feed from this camera.");
                }
            } else if (now - lastFrameTimeRef.current > frameTimeoutMs) {
                setIsConnecting(false);
                setHasError(true);
                setErrorMessage("Unable to retrieve video feed from this camera.");
            }
        }, 1500);

        function poll() {
            if (stopped) return;
            if (document.visibilityState === "hidden") {
                const onVisible = () => {
                    if (document.visibilityState === "visible") {
                        document.removeEventListener("visibilitychange", onVisible);
                        if (!stopped) poll();
                    }
                };
                document.addEventListener("visibilitychange", onVisible);
                return;
            }

            const t0_request = getCurrentTime();
            try {
                const server = getServers().getServer(serverIndex);
                if (!server) {
                    setIsConnecting(false);
                    setHasError(true);
                    setErrorMessage("Target server is offline or unreachable.");
                    return;
                }

                const cameraObj = server.getCamera(cameraIndex);
                if (!cameraObj) {
                    setIsConnecting(false);
                    setHasError(true);
                    setErrorMessage("Camera is offline or not configured.");
                    return;
                }

                cameraObj.pollImage(constantStreamID!)
                    .then(({ blob, capture_time }) => {
                        if (stopped) return;
                        if (!blob || blob.size === 0) {
                            setIsConnecting(false);
                            setHasError(true);
                            setErrorMessage("Camera returned an empty video frame.");
                            return;
                        }

                        lastFrameTimeRef.current = Date.now();
                        hasReceivedFirstFrameRef.current = true;
                        setIsConnecting(false);
                        setHasError(false);

                        const t0_network = getCurrentTime();
                        const t0_render = getCurrentTime();

                        const canvas = canvasRef.current;
                        if (!canvas) return;
                        const ctx = canvas.getContext("2d");
                        const img = new Image();

                        img.onload = function () {
                            if (stopped) return;
                            ctx!.drawImage(img, 0, 0, canvas.width, canvas.height);
                            if (canvas.width !== img.width || canvas.height !== img.height) {
                                canvas.width = img.width;
                                canvas.height = img.height;
                            }
                            URL.revokeObjectURL(img.src);
                            setIsConnecting(false);
                            setHasError(false);
                            measure(capture_time, t0_request, t0_network, t0_render);
                        };

                        img.onerror = function () {
                            if (stopped) return;
                            setIsConnecting(false);
                            setHasError(true);
                            setErrorMessage("Failed to decode video frame from camera.");
                        };

                        img.src = URL.createObjectURL(blob);

                        if (!stopped) {
                            poll();
                        }
                    })
                    .catch((err) => {
                        console.error("Camera poll error:", err);
                        if (!stopped) {
                            setIsConnecting(false);
                            setHasError(true);
                            setErrorMessage("Camera Stream Offline");
                            setTimeout(poll, 3000);
                        }
                    });
            } catch (err) {
                console.error("Camera setup error:", err);
                setIsConnecting(false);
                setHasError(true);
                setErrorMessage("Camera Stream Offline");
            }
        }

        poll();

        return () => {
            stopped = true;
            clearInterval(timeoutTimer);
            if (canvasRef.current) {
                const ctx = canvasRef.current.getContext("2d");
                if (ctx) {
                    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
                }
            }
        };
    }, [serverIndex, cameraIndex, constantStreamID]);

    const previousClientSize = useRef<{ width: number; height: number } | null>(null);
    const threshold = 0.5;
    const clientSizeWasSetForStreamId = useRef<string | null>(null);
    useEffect(() => {
        if (!constantStreamID || width <= 0 || height <= 0) return;
        const clientSizeHasNotChanged = previousClientSize.current &&
            Math.abs(previousClientSize.current.width - width) < threshold &&
            Math.abs(previousClientSize.current.height - height) < threshold;
        if (clientSizeHasNotChanged && constantStreamID === clientSizeWasSetForStreamId.current) {
            return;
        }
        clientSizeWasSetForStreamId.current = constantStreamID;
        try {
            getServers().getServer(serverIndex)?.setClientSize(constantStreamID, { width, height });
        } catch {
            // Ignore if server is offline
        }
        previousClientSize.current = { width, height };
    }, [serverIndex, cameraIndex, width, height, constantStreamID]);

    const handleRetry = () => {
        setIsConnecting(true);
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;
    };

    return (
        <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#0b1329" }}>
            <DisplayPerformanceData performanceData={performanceData} />
            <canvas
                ref={canvasRef}
                style={{
                    display: (hasError || isConnecting) ? "none" : "block",
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                }}
            >
                Your browser does not support HTML5 canvas.
            </canvas>

            {/* Connecting / Loading Spinner Overlay */}
            {isConnecting && !hasError && (
                <div
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "14px",
                        backgroundColor: "rgba(11, 19, 41, 0.88)",
                        backdropFilter: "blur(4px)",
                        color: "#f8fafc",
                        zIndex: 8,
                        padding: "20px",
                    }}
                >
                    <div style={{
                        width: "42px",
                        height: "42px",
                        borderRadius: "50%",
                        border: "3px solid rgba(56, 189, 248, 0.2)",
                        borderTopColor: "#38bdf8",
                        animation: "vci-spin 0.9s linear infinite"
                    }} />
                    <style>{`
                        @keyframes vci-spin {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                        }
                    `}</style>
                    <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#e2e8f0", letterSpacing: "0.02em" }}>
                            Connecting to Video Stream...
                        </div>
                        <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                            Initializing camera feed • Waiting for frame signal
                        </div>
                    </div>
                </div>
            )}

            {/* Error / No Signal Overlay */}
            {hasError && (
                <div
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "14px",
                        backgroundColor: "rgba(11, 19, 41, 0.94)",
                        backdropFilter: "blur(6px)",
                        padding: "24px 32px",
                        textAlign: "center",
                        zIndex: 10,
                    }}
                >
                    <div style={{
                        width: "52px",
                        height: "52px",
                        borderRadius: "50%",
                        backgroundColor: "rgba(239, 68, 68, 0.12)",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center"
                    }}>
                        <AlertTriangle size={28} color="#ef4444" />
                    </div>
                    <div>
                        <div style={{ fontSize: "15px", fontWeight: 700, color: "#f87171" }}>
                            NO SIGNAL / CAMERA OFFLINE
                        </div>
                        <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px", maxWidth: "340px" }}>
                            {errorMessage || "Unable to retrieve video feed from this camera. Check hardware connection or power."}
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={handleRetry}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            backgroundColor: "#0284c7",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "6px",
                            padding: "8px 18px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: "pointer",
                            marginTop: "6px",
                            boxShadow: "0 2px 8px rgba(2, 132, 199, 0.4)",
                        }}
                    >
                        <RefreshCw size={14} />
                        Retry Connection
                    </button>
                </div>
            )}
        </div>
    );
}
