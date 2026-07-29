import { useEffect, useState } from "react";
import { getVCI, ScriptInfo } from "../../network/vci-automation";

export function ScriptList({
    onSelectScript,
}: {
    onSelectScript: (script: ScriptInfo) => void;
}) {
    const [activeScript, setActiveScript] = useState<ScriptInfo | null>(null);
    const { scripts, isLoadingScripts, scriptsError } = useAvailableScripts();

    // When list is loaded, select the first script
    useEffect(() => {
        if (scripts.length === 0) return;
        if (activeScript && scripts.some((script) => script.id === activeScript.id)) return;
        setActiveScript(scripts[0] || null);
    }, [activeScript, scripts]);

    // Call onSelectScript when activeScript changes
    useEffect(() => {
        if (!activeScript) return;
        onSelectScript(activeScript);
    }, [activeScript, onSelectScript]);

    return (
        <>
            <h2 className="vci-script-list-title">Scripts</h2>
            {isLoadingScripts && <div className="text-muted text-center py-3">Loading scripts...</div>}
            {scriptsError && (
                <div className="text-danger small text-center py-2 px-1">{scriptsError}</div>
            )}
            <ul className="vci-script-list-items">
                {scripts.map((script) => (
                    <li
                        key={script.id}
                        className={`vci-script-item ${script.id === activeScript?.id ? "active" : ""}`}
                        onClick={() => setActiveScript(script)}
                    >
                        {script.name}
                    </li>
                ))}
                {!isLoadingScripts && scripts.length === 0 && (
                    <li className="vci-script-item text-muted" style={{ cursor: "default" }}>
                        No scripts available
                    </li>
                )}
            </ul>
        </>
    );
}

function useAvailableScripts() {
    const [scripts, setScripts] = useState<ScriptInfo[]>([]);
    const [isLoadingScripts, setIsLoadingScripts] = useState(false);
    const [scriptsError, setScriptsError] = useState<string | null>(null);

    useEffect(() => {
        setIsLoadingScripts(true);
        setScriptsError(null);

        setTimeout(() => {
            getVCI().getAvailableScripts()
                .then((availableScripts) => {
                    setScripts(availableScripts);
                })
                .catch((reason) => {
                    setScriptsError(reason instanceof Error ? reason.message : String(reason));
                })
                .finally(() => {
                    setIsLoadingScripts(false);
                });
        }, 200);
    }, []);

    return {
        scripts,
        isLoadingScripts,
        scriptsError,
    };
}
