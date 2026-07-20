import { useEffect, useState } from "react";
import { Card, ListGroup } from "react-bootstrap";
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
        if(scripts.length === 0) {
            return;
        }
        if(activeScript && scripts.some((script) => script.id === activeScript.id)) {
            return;
        }
        setActiveScript(scripts[0] || null);
    }, [activeScript, scripts]);

    // Call onSelectScript when activeScript changes
    useEffect(() => {
        if(!activeScript) {
            return;
        }
        onSelectScript(activeScript);
    }, [activeScript, onSelectScript]);

    return (
        <Card>
            <Card.Header>Scripts</Card.Header>
            {isLoadingScripts && <div className="px-3 pt-3 text-start">Loading scripts...</div>}
            {scriptsError &&
                <pre className="px-3 pt-3 mb-0 text-danger text-start">{scriptsError}</pre>
            }
            <ListGroup variant="flush">
                {scripts.map((script) => (
                    <ListGroup.Item
                        key={script.id}
                        action
                        active={script.id === activeScript?.id}
                        onClick={() => setActiveScript(script)}
                    >
                        {script.name}
                    </ListGroup.Item>
                ))}
                {!isLoadingScripts && scripts.length === 0 && (
                    <ListGroup.Item>No scripts available</ListGroup.Item>
                )}
            </ListGroup>
        </Card>
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
