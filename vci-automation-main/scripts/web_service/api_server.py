import traceback

import interceptor

from controller.logging_config import logger
from scripts import capture  # noqa: F401
from web_app_integration.api_handler import APIHandler


def main() -> None:
    try:
        port = 2525
        server = interceptor.Server(port)

        my_handler = APIHandler(server)
        server.set_handler(my_handler)

        logger.info(f"Starting Server on port {port}\n")
        server.run()
    except Exception as e:  # noqa: BLE001
        error_message = f"Error: {e}: {traceback.format_exc()}"
        logger.error(error_message)


if __name__ == "__main__":
    main()
