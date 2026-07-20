import { NoAutomaticRefreshes } from "../Components/WarningPopups.tsx";
import { ButtonWithKey } from "../Utility/KeyBindings";

export function About() {
  return (
    <>
      <div className="container pt-5">
        <h1>VCI Webapp</h1>
        <p>
          This is a web application to display and control video streams and
          cameras in the VCI.
        </p>
        <h2>About</h2>
        <p className="text-left">
          Press <b>h</b> or click <ButtonWithKey keybinding="h" /> in the
          navigation menu to open the help menu at anytime to list available
          operations and keybindings.
          <br />
          <br />
          If you hover over a button or long press it, the keybinding will be
          shown in square brackets <b>[]</b> as well as descriptions of the
          operation.
        </p>
        <NoAutomaticRefreshes />
      </div>
    </>
  );
}
