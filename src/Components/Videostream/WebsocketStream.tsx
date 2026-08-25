import { useRef, useState, useEffect, useCallback } from "react";
import { AlertTriangle, RefreshCw, Plus, Minus, RotateCcw, Target, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Maximize2, Sunrise, Sunset, Zap } from "lucide-react";
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
    enableInteractiveControls?: boolean;
    onResetView?: () => void;
}

const PAN_STEP = 0.05; // 0.05 normalized movement for D-Pad clicks (0.05 * 200 = 10px shift)

export function StreamWebsocket({
    serverIndex,
    cameraIndex,
    width,
    height,
    onStreamID,
    constantStreamID,
    autoStart = true,
    enableInteractiveControls = true,
    onResetView,
}: StreamProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const idOfRunningStream = useRef<string | null>(null);
    const [isConnecting, setIsConnecting] = useState(true);
    const [hasError, setHasError] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [showControls, setShowControls] = useState(false);

    const { performanceData, measure } = usePerformanceData();
    const lastFrameTimeRef = useRef<number>(Date.now());
    const hasReceivedFirstFrameRef = useRef<boolean>(false);

    // Mouse drag-to-pan state
    const [isDragging, setIsDragging] = useState(false);
    const dragStartRef = useRef<{ x: number; y: number } | null>(null);

    useEffect(() => {
        if (canvasRef.current) {
            const ctx = canvasRef.current.getContext("2d");
            if (ctx) {
                ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
            }
        }

        setIsConnecting(true);
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;

        if (!constantStreamID) return;

        idOfRunningStream.current = constantStreamID;
        let stopped = false;

        const startTime = Date.now();
        const initialGracePeriodMs = 12000;
        const frameTimeoutMs = 6000;

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
            // Ignore if offline
        }
        previousClientSize.current = { width, height };
    }, [serverIndex, cameraIndex, width, height, constantStreamID]);

    // ------------------------------------------------------------------
    // Interactive Zoom, Pan, Exposure & Trigger Handlers
    // ------------------------------------------------------------------
    const handleZoomIn = useCallback(() => {
        if (!constantStreamID) return;
        getServers().getServer(serverIndex)?.zoom_in(constantStreamID, 0.1);
    }, [serverIndex, constantStreamID]);

    const handleZoomOut = useCallback(() => {
        if (!constantStreamID) return;
        getServers().getServer(serverIndex)?.zoom_out(constantStreamID, 0.1);
    }, [serverIndex, constantStreamID]);

    const handleResetView = useCallback(() => {
        if (!constantStreamID) return;
        const server = getServers().getServer(serverIndex);
        server?.setZoomFactor(constantStreamID, 1);
        server?.resetZoomCenter(constantStreamID);
        server?.setStreamParameters(constantStreamID, {
            zoom_factor: 1,
            reset_zoom_center: true,
            fix_full_size: true,
        });
        if (onResetView) {
            onResetView();
        }
    }, [serverIndex, constantStreamID, onResetView]);

    const handleExposureUp = useCallback(() => {
        getServers().getServer(serverIndex)?.getCamera(cameraIndex)?.setParameterIncremental("exposure", 5000);
    }, [serverIndex, cameraIndex]);

    const handleExposureDown = useCallback(() => {
        getServers().getServer(serverIndex)?.getCamera(cameraIndex)?.setParameterIncremental("exposure", -5000);
    }, [serverIndex, cameraIndex]);

    const handleToggleTrigger = useCallback(() => {
        getServers().getServer(serverIndex)?.getCamera(cameraIndex)?.toggleTriggerSource();
    }, [serverIndex, cameraIndex]);

    const handlePan = useCallback((dx: number, dy: number) => {
        if (!constantStreamID) return;
        getServers().getServer(serverIndex)?.moveZoomCenterRel(constantStreamID, { x: dx, y: dy });
    }, [serverIndex, constantStreamID]);

    // Mouse wheel zoom
    const handleWheel = (e: React.WheelEvent) => {
        if (!enableInteractiveControls || !constantStreamID) return;
        if (e.deltaY < 0) {
            handleZoomIn();
        } else if (e.deltaY > 0) {
            handleZoomOut();
        }
    };

    // Mouse drag-to-pan
    const handleMouseDown = (e: React.MouseEvent) => {
        if (!enableInteractiveControls || !constantStreamID) return;
        setIsDragging(true);
        dragStartRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDragging || !dragStartRef.current || !constantStreamID) return;
        const dx = (e.clientX - dragStartRef.current.x) * 3;
        const dy = (e.clientY - dragStartRef.current.y) * 3;
        dragStartRef.current = { x: e.clientX, y: e.clientY };
        handlePan(-dx, -dy);
    };

    const handleMouseUp = () => {
        setIsDragging(false);
        dragStartRef.current = null;
    };

    const handleRetry = () => {
        setIsConnecting(true);
        setHasError(false);
        setErrorMessage(null);
        lastFrameTimeRef.current = Date.now();
        hasReceivedFirstFrameRef.current = false;
    };

    return (
        <div
            style={{
                position: "relative",
                width: width ? `${width}px` : "100%",
                height: height ? `${height}px` : "100%",
                maxWidth: "100%",
                maxHeight: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: "#0b1329",
                borderRadius: "8px",
                overflow: "hidden",
                boxShadow: "0 4px 12px rgba(0, 0, 0, 0.2)",
            }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
        >
            <DisplayPerformanceData performanceData={performanceData} />

            {/* HTML5 Canvas Rendering Target */}
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "contain",
                    display: (hasError || isConnecting) ? "none" : "block",
                    cursor: isDragging ? "grabbing" : enableInteractiveControls ? "grab" : "default",
                }}
            >
                Your browser does not support HTML5 canvas.
            </canvas>

            {/* Floating On-Screen D-Pad & Control Overlay */}
            {enableInteractiveControls && !hasError && !isConnecting && (
                <div className="ps-stream-controls-overlay">
                    <div className="ps-zoom-quick-row">
                        <button
                            type="button"
                            className="ps-zoom-btn"
                            onClick={handleZoomIn}
                            title="Zoom In (+)"
                        >
                            <Plus size={13} />
                        </button>
                        <button
                            type="button"
                            className="ps-zoom-btn"
                            onClick={handleZoomOut}
                            title="Zoom Out (-)"
                        >
                            <Minus size={13} />
                        </button>
                    </div>

                    <div className="ps-zoom-quick-row">
                        <button
                            type="button"
                            className="ps-zoom-btn"
                            onClick={handleExposureUp}
                            title="Exposure Up (+5000) [w]"
                        >
                            <Sunrise size={12} />
                        </button>
                        <button
                            type="button"
                            className="ps-zoom-btn"
                            onClick={handleExposureDown}
                            title="Exposure Down (-5000) [s]"
                        >
                            <Sunset size={12} />
                        </button>
                        <button
                            type="button"
                            className="ps-zoom-btn"
                            onClick={handleToggleTrigger}
                            title="Toggle Trigger Source [t]"
                        >
                            <Zap size={12} />
                        </button>
                    </div>

                    <div className="ps-dpad-grid">
                        <div />
                        <button
                            type="button"
                            className="ps-dpad-btn"
                            onClick={() => handlePan(0, -PAN_STEP)}
                            title="Pan Up (Fine)"
                        >
                            <ChevronUp size={14} />
                        </button>
                        <div />

                        <button
                            type="button"
                            className="ps-dpad-btn"
                            onClick={() => handlePan(-PAN_STEP, 0)}
                            title="Pan Left (Fine)"
                        >
                            <ChevronLeft size={14} />
                        </button>
                        <button
                            type="button"
                            className="ps-dpad-btn"
                            onClick={handleResetView}
                            title="Center & Reset View"
                        >
                            <RotateCcw size={12} />
                        </button>
                        <button
                            type="button"
                            className="ps-dpad-btn"
                            onClick={() => handlePan(PAN_STEP, 0)}
                            title="Pan Right (Fine)"
                        >
                            <ChevronRight size={14} />
                        </button>

                        <div />
                        <button
                            type="button"
                            className="ps-dpad-btn"
                            onClick={() => handlePan(0, PAN_STEP)}
                            title="Pan Down (Fine)"
                        >
                            <ChevronDown size={14} />
                        </button>
                        <div />
                    </div>
                </div>
            )}

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
