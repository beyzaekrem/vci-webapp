import Settings from "../Components/Config/Settings.tsx";

export function ConfigPage() {
  return (
    <div
      style={{ height: "100%" }}
      className="d-flex justify-content-center"
    >
      <div>
        <h1 className="mt-4">Settings</h1>
        <Settings />
      </div>
    </div>
  );
}
