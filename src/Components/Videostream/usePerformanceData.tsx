import { useRef, useState } from "react";
import { useKeyPress } from "../../Utility/KeyBindings";
import { infoIcon, performanceIcon } from "../Icons";
import { InfoPopUp } from "../../Utility/UI";

/**
 * Performance data, all times in seconds.
 */
type PerfData = {
    frameCount: number;
    avgNetworkDelay: number;   // one-way: receive − server capture
    avgRenderTime: number;     // render end − render start
    avgRoundtripTime: number;  // receive − request send
    instantFps: number;        // frames in last 1s
    averageFps: number;        // total frames ÷ total seconds
};

export function usePerformanceData() {
    const startTimeRef = useRef<number>(getCurrentTime());
    const frameTimesRef = useRef<number[]>([]);

    const [performanceData, setPerformance] = useState<PerfData>({
        frameCount: 0,
        avgNetworkDelay: 0,
        avgRenderTime: 0,
        avgRoundtripTime: 0,
        instantFps: 0,
        averageFps: 0,
    });

    /**
     * @param capture_time   server timestamp when frame was captured
     * @param t0_request     client timestamp when request was SENT
     * @param t0_network     client timestamp when frame was RECEIVED
     * @param t0_render      client timestamp when rendering started
     */
    function measure(
        capture_time: number,
        t0_request: number,
        t0_network: number,
        t0_render: number
    ) {
        const t1_render = getCurrentTime();
        const renderTime = t1_render - t0_render;
        const networkDelay = t0_network - capture_time;
        const roundtripTime = t0_network - t0_request;

        const now = getCurrentTime();
        frameTimesRef.current.push(now);
        frameTimesRef.current = frameTimesRef.current.filter(ts => now - ts <= 1);
        const instantFps = frameTimesRef.current.length;

        setPerformance(prev => {
            const newCount = prev.frameCount + 1;
            const avgNetworkDelay =
                (prev.avgNetworkDelay * prev.frameCount + networkDelay) / newCount;
            const avgRenderTime =
                (prev.avgRenderTime * prev.frameCount + renderTime) / newCount;
            const avgRoundtripTime =
                (prev.avgRoundtripTime * prev.frameCount + roundtripTime) / newCount;
            const elapsedSec = now - startTimeRef.current;
            const averageFps = newCount / elapsedSec;

            return {
                frameCount: newCount,
                avgNetworkDelay,
                avgRenderTime,
                avgRoundtripTime,
                instantFps,
                averageFps,
            };
        });
    }

    return {
        performanceData,
        measure,
    };
}

export function DisplayPerformanceData({
    performanceData,
}: {
    performanceData: PerfData;
}) {
    const [display, setDisplay] = useState(false);

    useKeyPress({
        key: "F2",
        onKeyEvent: () => setDisplay(d => !d),
        description: "Display Performance Data (FPS and delays)",
        category: "General",
        icon: performanceIcon,
    });

    if(!display) return null;

    const d = 5; // decimal places

    return (
        <div
            style={{
                position: "absolute",
                bottom: 0,
                color: "green",
                backgroundColor: "rgba(0,0,0,0.5)",
                padding: "5px",
                zIndex: 10,
                textAlign: "left",
            }}
        >
            <InfoPopUp longTitle="Frame Count" content="Number of frames rendered since page load">
                <p className="mb-0">
                    {infoIcon} Frame count: {performanceData.frameCount}
                </p>
            </InfoPopUp>

            <InfoPopUp
                longTitle="Average Network Delay"
                content={
                    <p>
                        Time between when the server captured the frame and when you received it.
                        Note that this is wrong in production because <b> client and server clocks are not synchronized. </b>
                        See <b>Average Round-Trip Time</b> for a more accurate measure of network delay.
                    </p>
                }
            >
                <p className="mb-0">
                    {infoIcon} Avg network delay:{" "}
                    {performanceData.avgNetworkDelay.toFixed(d)} s
                </p>
            </InfoPopUp>

            <InfoPopUp
                longTitle="Average Round-Trip Time"
                content={
                    <p>
                        Time between when you sent the request and when the frame arrived.
                    </p>
                }
            >
                <p className="mb-0">
                    {infoIcon} Avg round-trip:{" "}
                    {performanceData.avgRoundtripTime.toFixed(d)} s
                </p>
            </InfoPopUp>

            <InfoPopUp
                longTitle="Average Render Time"
                content={<p>Time to paint the image once it’s in memory.</p>}
            >
                <p className="mb-0">
                    {infoIcon} Avg render time:{" "}
                    {performanceData.avgRenderTime.toFixed(d)} s
                </p>
            </InfoPopUp>

            <InfoPopUp
                longTitle="Instant FPS"
                content={<p>Frames rendered in the last second.</p>}
            >
                <p className="mb-0">
                    {infoIcon} Instant FPS: {performanceData.instantFps}
                </p>
            </InfoPopUp>

            <InfoPopUp
                longTitle="Average FPS"
                content={<p>Frames per second since the page loaded.</p>}
            >
                <p className="mb-0">
                    {infoIcon} Average FPS:{" "}
                    {performanceData.averageFps.toFixed(d)}
                </p>
            </InfoPopUp>
        </div>
    );
}

/**
 * @returns current time in seconds since epoch
 */
export function getCurrentTime(): number {
    const origin = performance.timeOrigin || performance.timing.navigationStart;
    return (origin + performance.now()) / 1000;
}
