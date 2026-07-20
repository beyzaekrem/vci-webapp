import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode, UIEvent } from "react";

const BOTTOM_THRESHOLD_PX = 24;

type AutoScrollFollowProps = {
    children: ReactNode;
    followTrigger: number;
    className?: string;
    style?: CSSProperties;
};

export function AutoScrollFollow({
    children,
    followTrigger,
    className,
    style,
}: AutoScrollFollowProps) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [isFollowing, setIsFollowing] = useState(true);

    const updateFollowState = (element: HTMLDivElement) => {
        const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
        setIsFollowing(distanceFromBottom <= BOTTOM_THRESHOLD_PX);
    };

    const handleScroll = (event: UIEvent<HTMLDivElement>) => {
        updateFollowState(event.currentTarget);
    };

    useEffect(() => {
        const element = containerRef.current;
        if (!element || !isFollowing) {
            return;
        }

        element.scrollTop = element.scrollHeight;
    }, [followTrigger, isFollowing]);

    return (
        <div
            ref={containerRef}
            className={className}
            style={style}
            onScroll={handleScroll}
        >
            {children}
        </div>
    );
}
