import { getServers } from "../../network/capture-server";
import { useKeyPress, ButtonWithKey } from "../../Utility/KeyBindings";
import { useLocallyStored } from "../../Utility/Storage";
import { nextItem, previousItem } from "./Icons";
import Select from "react-select";

/*==============================================================================
  Menu for selecting a server
==============================================================================*/

export function SelectServer({ serverIdKey }: { serverIdKey: string; }) {
    return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
            <MoveServerIndexButton increment={-1} serverIdKey={serverIdKey} />
            <SelectServerDropdown serverIdKey={serverIdKey} />
            <MoveServerIndexButton increment={1} serverIdKey={serverIdKey} />
        </div>
    );
} export function MoveServerIndexButton({
    increment, serverIdKey,
}: {
    increment: number;
    serverIdKey: string;
}) {
    const [currentServerId, setServer] = useLocallyStored<number>(serverIdKey, 0);
    const key = increment > 0 ? "e" : "w";
    const icon = increment > 0 ? nextItem : previousItem;

    function move() {
        const serverCount = getServers().servers.length;
        const newIndex = (currentServerId + increment + serverCount) % serverCount;
        setServer(newIndex);
    }

    useKeyPress({
        key,
        description: increment > 0 ? "Next Server" : "Previous Server",
        onKeyEvent: move,
        category: "General",
        icon,
        dependencies: [currentServerId],
    });

    return <ButtonWithKey keybinding={key} />;
}


export function SelectServerDropdown({ serverIdKey }: { serverIdKey: string }) {
    const [serverIndex, setServer] = useLocallyStored<number>(serverIdKey, 0);
    const servers = getServers();
    const options = servers.servers.map((server, index) => ({
        value: index,
        label: `Server ${index + 1} (${server.getDomain()})`,
    }));
    const currentValue = options.find((option) => option.value === serverIndex);
    return (
        <div style={{ zIndex: 200 }}>
            <Select
                options={options}
                value={currentValue}
                onChange={(v) => {
                    if(!v) return;
                    setServer(v.value);
                }}
            />
        </div>
    );
}
