import { Button } from "react-bootstrap";
import { getServers } from "../../network/capture-server";
import {
  useState,
  ReactNode
} from "react";
import { AlertModalButton } from "../../Utility/UI";
import { InfoPopUpBadge } from "../../Utility/UI";
import Select from "react-select";
import { RecordingProvider, useRecordingContext } from "./RecordingProvider.tsx";

export function CaptureMenu() {
  const [mode, setMode] = useState<CaptureMode>(CaptureMode.SINGLE_IMAGE);
  return (
    <RecordingProvider>
      <CaptureModeSelector mode={mode} setMode={setMode} />
      {
        mode === CaptureMode.SINGLE_IMAGE && <>
          <SingleRecordingControl />
          <hr />
        </>
      }
      <RecordingList />
    </RecordingProvider>
  );
}

enum CaptureMode {
  SINGLE_IMAGE = "Record Single Image",
  COMING_SOON = "More Coming Soon"
}

function CaptureModeSelector({ mode, setMode }: { mode: CaptureMode; setMode: React.Dispatch<React.SetStateAction<CaptureMode>> }): ReactNode {
  return <>
    <h3>Capture Mode</h3>
    <div style={{ marginTop: 8, marginBottom: 16, maxWidth: 400, marginLeft: "auto", marginRight: "auto" }}>
      <Select
        options={Object.values(CaptureMode).map((mode) => ({
          value: mode,
          label: mode
        }))}
        value={{ value: mode, label: mode }}
        onChange={(selected) => {
          if(selected) {
            setMode(selected.value as CaptureMode);
          }
        }} />
    </div>
  </>;
}

/**
 * return current date in format YYYY-MM-DD
 */
function getDateTimeString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');

  return `${year}_${month}_${day}`;
}

function getDefaultRecordingName() {
  return getDateTimeString() + "_from_webapp";
}

/**
 * Control to start a single recording with a given name.
 */
function SingleRecordingControl() {
  const { recordings, refreshRecordings } = useRecordingContext();
  const [recordingName, setRecordingName] = useState(getDefaultRecordingName());

  const recordingExists = recordings.some(r => r.name === recordingName);

  return <>
    <h3>Record One Frame</h3>
    <InfoPopUpBadge
      title="What does this do?"
      longTitle="Recording One Frame"
      content={
        <>
          This will instantly record one frame from all connected cameras and store it on the capture servers with the given name.
          <br />
          Uses single image mode.
        </>
      }
    />
    <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "center" }}>
        <input
          id="recordName"
          type="text"
          value={recordingName}
          onChange={(e) => setRecordingName(e.target.value)}
          style={{ width: 400 }}
        />
        <SingleRecordingFull recordingName={recordingName} setRecordingName={setRecordingName} />
      </div>
      {
        recordingExists && <span style={{ color: "red" }}>Recording with this name already exists!</span>
      }
    </div>
  </>
}

function SingleRecordingFull({ recordingName, setRecordingName }: { recordingName: string; setRecordingName: React.Dispatch<React.SetStateAction<string>> }) {
  const { recordings, refreshRecordings } = useRecordingContext();
  const recordingExists = recordings.some(r => r.name === recordingName);

  function record() {
    // if no name is given, use default
    var name = recordingName
    if(recordingName.length === 0) {
      name = getDefaultRecordingName();
      setRecordingName(name);
    }

    // after recording, refresh recordings via context
    getServers()
      .recordSingle(name)
      .catch((err) => {
        console.warn("record failed", err);
      })
      .finally(() => {
        refreshRecordings();
      });
  }
  return <>
    {
      recordingExists ? <>
        <AlertModalButton
          buttonText="Record"
          title="Overwrite Recording?"
          message={
            <>
              A recording with the name <br /> <b>{recordingName}</b> already exists.
              <br />
              Do you want to overwrite it?
            </>
          }
          onAccept={record}
        />
      </>
        : <Button onClick={record}>Record</Button>
    }
  </>
}

//TODO finish this, have 2 steps prepare and record
function SingleRecordingTimed({ recordingName, recordingExists }: { recordingName: string; recordingExists: boolean; }) {
  const [overWriteRecording, setOverWriteRecording] = useState(false);

  return <>
    {
      recordingExists && overWriteRecording === false && <AlertModalButton
        buttonText="Overwrite when Recording"
        title="Overwrite Existing Recording?"
        message={
          <>
            A recording with the name <b>{recordingName}</b> already exists.
            <br />
            Do you want to overwrite it when you start recording?
          </>
        }
        onAccept={() => {
          setOverWriteRecording(true);
        }}
      />
    }
    <Button
      variant="primary"
      disabled={recordingExists && !overWriteRecording}
      onClick={() => {
      }}
    >
      Record
    </Button>
  </>
}

/**
 * List all current recordings from server.
 * Allows user to delete recordings.
 */
function RecordingList() {
  const { recordings, refreshRecordings } = useRecordingContext();

  return <>
    <h3>Current Recordings</h3>
    <div
      key="recordings-scroll-container"
      style={{
        maxHeight: "50vh",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        border: "1px solid rgba(0,0,0,0.1)",
        borderRadius: 4,
        maxWidth: 800,
        padding: 15,
        marginLeft: "auto",
        marginRight: "auto"
      }}
    >
      {recordings.map((rr) => {
        const showServerWarning = rr.availability.presentOnServers.length !== getServers().servers.length;
        return <div
          key={rr.name}
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span style={{ wordBreak: "break-all" }}>{rr.name}</span>
          <div style={{ marginLeft: "auto" }}></div>
          {
            showServerWarning &&
            <InfoPopUpBadge
              title={`Available on ${rr.availability.presentOnServers.length} of ${getServers().servers.length} servers`}
              bg="warning"
              content={
                <>
                  <p>
                    This recording is missing from servers:
                  </p>
                  <ul>
                    {getServers().servers.map((s, index) => {
                      const serverName = `Server ${index + 1} (${s.getDomain()})`;
                      if(!rr.availability.presentOnServers.includes(serverName)) {
                        return <li key={serverName}>{serverName}</li>;
                      }
                      return null;
                    })}
                  </ul>
                  <p>
                    This may indicate an issue with some capture servers during recording.
                  </p>
                </>
              }
            />
          }
          <AlertModalButton
            buttonText="Delete"
            title="Delete Recording"
            message={
              <>
                Are you sure you want to delete the recording <br /> <b>{rr.name}</b>?
              </>
            }
            onAccept={() => {
              getServers().allPromise((server) => server.deleteRecording(rr.name)).finally(() => {
                refreshRecordings();
              });
            }}
          />
        </div>
      })}
    </div>
  </>
}