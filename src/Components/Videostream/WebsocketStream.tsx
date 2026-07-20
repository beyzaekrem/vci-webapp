import { useRef, useState, useEffect } from "react";
import { getServers } from "../../network/capture-server";
import { usePerformanceData, DisplayPerformanceData, getCurrentTime } from "./usePerformanceData";


export interface StreamProps {
    serverIndex: number,
    cameraIndex: number,
    width: number,
    height: number,
    onStreamID?: (id: string) => void,
    constantStreamID: string | null,
    autoStart?: boolean
}

//TODO verify that we correctly trash the frame when the next one is rendered and check that the browser cache is not flooded with images

export function StreamWebsocket({
    serverIndex, cameraIndex, width, height, onStreamID, constantStreamID, autoStart = true
}: StreamProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const idOfRunningStream = useRef<string | null>(null); // id of the stream that is currently running, might not be the same as parameter
    const [streamInitialized, setS] = useState(false)

    const { performanceData, measure } = usePerformanceData();

    useEffect(() => {
        if(streamInitialized && idOfRunningStream.current === constantStreamID) {
            return;
        }
        if(!constantStreamID) {
            return;
        }
        setS(true);
        idOfRunningStream.current = constantStreamID;
        let stopped = false;

        function poll() {
            if(stopped) return;
            // Pause polling when the browser tab is not visible to reduce server load
            if(document.visibilityState === "hidden") {
                const onVisible = () => {
                    if(document.visibilityState === "visible") {
                        document.removeEventListener("visibilitychange", onVisible);
                        if(!stopped) poll();
                    }
                };
                document.addEventListener("visibilitychange", onVisible);
                return;
            }
            const t0_request = getCurrentTime();
            getServers()
                .getServer(serverIndex)
                .getCamera(cameraIndex)
                .pollImage(constantStreamID!).then(({ blob, capture_time }) => {
                    const t0_network = getCurrentTime()
                    const t0_render = getCurrentTime()

                    // Example: draw image to canvas
                    const canvas = canvasRef.current;
                    if(!canvas) return;
                    const ctx = canvas.getContext("2d");

                    const img = new Image();

                    img.onload = function () {
                        // Draw the image onto the canvas
                        ctx!.drawImage(img, 0, 0, canvas.width, canvas.height);

                        // Set the canvas dimensions to match the image dimensions
                        if(canvas.width != img.width || canvas.height != img.height) {
                            canvas.width = img.width;
                            canvas.height = img.height;
                        }

                        // Clean up the object URL
                        URL.revokeObjectURL(img.src);

                        // Measure performance
                        measure(capture_time, t0_request, t0_network, t0_render);
                    };

                    // Create a URL for the image and set it as the image source
                    img.src = URL.createObjectURL(blob);

                    // Continue polling
                    if(!stopped) {
                        poll();
                    }
                });
        }

        poll();

        return () => {
            stopped = true;
        };
    }, [serverIndex, cameraIndex, constantStreamID]);

    const previousClientSize = useRef<{ width: number, height: number } | null>(null);
    const threshold = 0.5; // only update if size changes more than this threshold
    const clientSizeWasSetForStreamId = useRef<string | null>(null);
    useEffect(() => {
        if(!constantStreamID) {
            return;
        }
        const clientSizeHasNotChanged = previousClientSize.current &&
            Math.abs(previousClientSize.current.width - width) < threshold &&
            Math.abs(previousClientSize.current.height - height) < threshold;
        if(clientSizeHasNotChanged && constantStreamID === clientSizeWasSetForStreamId.current) {
            return; // no need to update if the size or streamid has not changed
        }
        clientSizeWasSetForStreamId.current = constantStreamID;
        getServers().getServer(serverIndex).setClientSize(constantStreamID, { width, height });
        previousClientSize.current = { width, height };
    }, [serverIndex, cameraIndex, width, height, constantStreamID]);

    return <>
        <DisplayPerformanceData performanceData={performanceData} />
        <canvas ref={canvasRef}>
            Your browser does not support the HTML5 canvas tag.
        </canvas>
    </>
}
