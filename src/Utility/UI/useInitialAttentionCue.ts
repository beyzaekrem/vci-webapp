import { useCallback, useEffect, useRef, useState } from "react";

export type InitialAttentionCueOptions = {
    enabled?: boolean;
    animationDurationMs?: number;
    persistAnimation?: boolean;
    scrollDelayMs?: number;
    scrollBlock?: ScrollLogicalPosition;
};

export type InitialAttentionCueResult<T extends HTMLElement> = {
    targetRef: (element: T | null) => void;
    isAttentionActive: boolean;
};

export function useInitialAttentionCue<T extends HTMLElement>({
    enabled = true,
    animationDurationMs = 2200,
    persistAnimation = false,
    scrollDelayMs = 150,
    scrollBlock = "center",
}: InitialAttentionCueOptions = {}): InitialAttentionCueResult<T> {
    const [targetElement, setTargetElement] = useState<T | null>(null);
    const hasActivatedRef = useRef(false);
    const [isAttentionActive, setIsAttentionActive] = useState(false);
    const targetRef = useCallback((element: T | null) => {
        setTargetElement(element);
    }, []);

    useEffect(() => {
        if(!enabled || !targetElement || hasActivatedRef.current) {
            return;
        }

        hasActivatedRef.current = true;

        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        setIsAttentionActive(true);

        const scrollTimer = window.setTimeout(() => {
            targetElement.scrollIntoView({
                behavior: prefersReducedMotion ? "auto" : "smooth",
                block: scrollBlock,
                inline: "nearest",
            });
        }, scrollDelayMs);

        if (persistAnimation) {
            return () => {
                window.clearTimeout(scrollTimer);
            };
        }

        const animationTimer = window.setTimeout(() => {
            setIsAttentionActive(false);
        }, animationDurationMs);

        return () => {
            window.clearTimeout(scrollTimer);
            window.clearTimeout(animationTimer);
        };
    }, [animationDurationMs, enabled, persistAnimation, scrollBlock, scrollDelayMs, targetElement]);

    return { targetRef, isAttentionActive };
}
