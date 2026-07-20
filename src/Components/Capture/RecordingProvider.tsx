import { createContext, ReactNode, useState, useEffect, useContext } from "react";
import { getServers } from "../../network/capture-server";

type Recording = {
    name: string;
    availability: {
        presentOnServers: string[];
    };
};
interface RecordingContextType {
    recordings: Recording[];
    refreshRecordings: () => void;
}
const RecordingContext = createContext<RecordingContextType>({
    recordings: [],
    refreshRecordings: () => { }
});

/**
 * Provider for recording context. Contains list of recordings and function to refresh the list.
 */
export function RecordingProvider({ children }: { children: ReactNode; }) {
    const [recordings, setRecordings] = useState<Recording[]>([]);

    function refreshRecordings() {
        // list recordings from first server
        getServers().allPromise((server) => server.listRecordings()).then((allRecordings) => {
            const recordings: Recording[] = [];
            allRecordings.forEach((recList, serverIndex) => {
                if(!recList) return;
                recList.forEach((rec) => {
                    let existing = recordings.find(r => r.name === rec);
                    if(!existing) {
                        existing = {
                            name: rec,
                            availability: {
                                presentOnServers: []
                            }
                        };
                        recordings.push(existing);
                    }
                    existing.availability.presentOnServers.push(`Server ${serverIndex + 1} (${getServers().servers[serverIndex].getDomain()})`);
                });
            });
            setRecordings(recordings.sort((a, b) => a.name.localeCompare(b.name)));
        });
    }

    useEffect(() => {
        refreshRecordings();
    }, []);

    return (
        <RecordingContext.Provider value={{ recordings, refreshRecordings }}>
            {children}
        </RecordingContext.Provider>
    );
}

/**
 * Hook to access recording context.
 * Contains list of recordings and function to refresh the list.
 */
export function useRecordingContext() {
    return useContext(RecordingContext);
}
