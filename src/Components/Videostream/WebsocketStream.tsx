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
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;

        if (!constantStreamID) {
            return;
        }

        idOfRunningStream.current = constantStreamID;
        let stopped = false;

        // 3. Timeout check: if no frame is received within 4.5 seconds, flag as offline
        const timeoutTimer = setInterval(() => {
            if (stopped) return;
            if (!hasReceivedFirstFrameRef.current || Date.now() - lastFrameTimeRef.current > 4500) {
                setHasError(true);
                setErrorMessage("Unable to retrieve video feed from this camera.");
            }
        }, 2000);

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
                    setHasError(true);
                    setErrorMessage("Target server is offline or unreachable.");
                    return;
                }

                const cameraObj = server.getCamera(cameraIndex);
                if (!cameraObj) {
                    setHasError(true);
                    setErrorMessage("Camera is offline or not configured.");
                    return;
                }

                cameraObj.pollImage(constantStreamID!)
                    .then(({ blob, capture_time }) => {
                        if (stopped) return;
                        if (!blob || blob.size === 0) {
                            setHasError(true);
                            setErrorMessage("Camera returned an empty video frame.");
                            return;
                        }

                        lastFrameTimeRef.current = Date.now();
                        hasReceivedFirstFrameRef.current = true;
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
                            measure(capture_time, t0_request, t0_network, t0_render);
                        };

                        img.onerror = function () {
                            if (stopped) return;
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
                            setHasError(true);
                            setErrorMessage("Camera Stream Offline");
                            setTimeout(poll, 3000);
                        }
                    });
            } catch (err) {
                console.error("Camera setup error:", err);
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
        if (!constantStreamID) return;
        const clientSizeHasNotChanged = previousClientSize.current &&
            Math.abs(previousClientSize.current.width - width) < threshold &&
            Math.abs(previousClientSize.current.height - height) < threshold;
        if (clientSizeHasNotChanged && constantStreamID === clientSizeWasSetForStreamId.current) {
            return;
        }
        clientSizeWasSetForStreamId.current = constantStreamID;
        try {
            getServers().getServer(serverIndex).setClientSize(constantStreamID, { width, height });
        } catch {
            // Ignore if server is offline
        }
        previousClientSize.current = { width, height };
    }, [serverIndex, cameraIndex, width, height, constantStreamID]);

    const handleRetry = () => {
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;
    };

    return (
        <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <DisplayPerformanceData performanceData={performanceData} />
            <canvas
                ref={canvasRef}
                style={{
                    display: hasError ? "none" : "block",
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                }}
            >
                Your browser does not support HTML5 canvas.
            </canvas>

            {hasError && (
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "12px",
                        color: "#ef4444",
                        backgroundColor: "rgba(11, 19, 41, 0.95)",
                        padding: "24px 32px",
                        borderRadius: "12px",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5)",
                        textAlign: "center",
                        maxWidth: "90%",
                        zIndex: 10,
                    }}
                >
                    <AlertTriangle size={38} color="#ef4444" />
                    <div>
                        <div style={{ fontSize: "16px", fontWeight: 700, color: "#f87171" }}>
                            Camera Stream Offline
                        </div>
                        <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                            {errorMessage || "Unable to retrieve video feed from this camera."}
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
                            padding: "8px 16px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: "pointer",
                            marginTop: "8px",
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
