import { useState, useEffect } from "react";


export function useClientSize(ref: React.RefObject<HTMLDivElement>) {
    const [divSize, setDivSize] = useState({ width: 0, height: 0 });

    function newClientSize() {
        if(!ref.current) return;
        console.log("client resize to " + ref.current.clientWidth + "x" + ref.current.clientHeight);
        setDivSize({
            width: ref.current.clientWidth,
            height: ref.current.clientHeight,
        });
    }

    useEffect(() => {
        const resizeObserver = new ResizeObserver((entries) => {
            newClientSize();
            for(let entry of entries) {
                console.log("resize observed");
            }
        });

        if(ref.current) {
            resizeObserver.observe(ref.current);
        }

        return () => {
            if(ref.current) {
                resizeObserver.unobserve(ref.current);
            }
        };
    }, [ref]);

    useEffect(() => {
        newClientSize();
    }, [ref.current]);

    return divSize;
}
