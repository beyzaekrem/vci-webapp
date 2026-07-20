import { InfoPopUpBadge } from "../Utility/UI";

/**
 * This is a warning popup to inform the user that the webclient does not
 * automatically refresh the data.
 */
export function NoAutomaticRefreshes() {
    return (
        <InfoPopUpBadge
            placement="bottom"
            longTitle="No Automatic Refreshes"
            title="No Automatic Refreshes"
            content={<p>
                In the current state of development, the server does not notify the
                webclient if something changes. You might have to{" "}
                <b>refresh the page</b> to get the most recent data, e.g. after
                setting parameters or starting a stream. This is only temporary to get
                the basic functionality working for now.
            </p>} />
    );
}
