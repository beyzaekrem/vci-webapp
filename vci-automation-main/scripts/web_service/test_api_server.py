import threading
import time

import api_server
import interceptor


def main():
    w = WebAppMock()
    scripts = w.get_dict_from_responses(w.send("SCRIPT_OVERVIEW")).get("scripts")

    schema = w.get_dict_from_responses(w.send("GET_SCRIPT_SCHEMA", {"script_name": scripts[0]}))

    w.send(
        "RUN_SCRIPT",
        {
            "script_name": "scripts.capture.example_script",
            "arguments": "--server 1 2 --flag --exposure 2",
        },
    )


class WebAppMock:
    def __init__(self):
        print("Connecting...")
        self.client = interceptor.Client("localhost", 2443)
        self.client.run(blocking=False)
        self.client.wait_for_connection(1000)

    @staticmethod
    def get_dict_from_responses(responses: list[interceptor.MessageIn], payload_index: int = 0) -> list[dict] | dict:
        if isinstance(responses, list):
            return [response.payload[payload_index].ToDict() for response in responses]
        return responses.payload[payload_index].ToDict()

    def send(self, path: str, parameters: dict | None = None) -> interceptor.MessageIn:
        if parameters is None:
            message = interceptor.MessageOut(path)
        else:
            parameters = interceptor.Payload.FromDict(parameters)
            message = interceptor.MessageOut(path, [parameters])

        promise = self.client.async_send(message)
        return promise.wait()


if __name__ == "__main__":
    threading.Thread(target=api_server.main).start()
    time.sleep(1)
    main()
