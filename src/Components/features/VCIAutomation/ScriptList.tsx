import { useEffect, useState } from "react";
import { getVCI, ScriptInfo } from "../../../network/vci-automation";

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

    const [dropdownOpen, setDropdownOpen] = useState(false);

    return (
        <>
            {/* Mobile View: Custom Active Script Picker Card */}
            <div className="vci-mobile-script-select-container">
                <label className="vci-mobile-script-label">ACTIVE SCRIPT</label>
                <div className="vci-mobile-select-wrapper">
                    <button
                        type="button"
                        className={`vci-mobile-script-trigger-btn ${dropdownOpen ? "open" : ""}`}
                        onClick={() => setDropdownOpen((prev) => !prev)}
                    >
                        <div className="vci-mobile-script-trigger-text">
                            <span className="vci-script-trigger-name">{activeScript?.name || "Select Script"}</span>
                        </div>
                        <span className={`vci-script-trigger-arrow ${dropdownOpen ? "expanded" : ""}`}>▾</span>
                    </button>

                    {/* Custom Styled In-Place Mobile Dropdown List */}
                    {dropdownOpen && (
                        <div className="vci-mobile-script-dropdown-menu">
                            <div className="vci-mobile-dropdown-list">
                                {scripts.map((s) => {
                                    const isSelected = s.id === activeScript?.id;
                                    return (
                                        <button
                                            key={s.id}
                                            type="button"
                                            className={`vci-mobile-dropdown-item ${isSelected ? "selected" : ""}`}
                                            onClick={() => {
                                                setActiveScript(s);
                                                setDropdownOpen(false);
                                            }}
                                        >
                                            <span className="vci-dropdown-item-name">{s.name}</span>
                                            {isSelected && <span className="vci-dropdown-item-check">✓</span>}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Desktop View: Script List Card */}
            <div className="vci-desktop-script-list">
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
            </div>
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
