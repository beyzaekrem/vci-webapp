from __future__ import annotations

import interceptor


class Handler(interceptor.MessageHandler):

    def __init__(self) -> None:
        interceptor.MessageHandler.__init__(self)
        self.connections = []

    def OnConnect(self, connection: interceptor.Connection) -> None:
        print(f"[server.py] Handler::OnConnect (connection={connection})")
        self.connections.append(connection)

    def OnDisconnect(self, connection: interceptor.Connection, graceful: bool) -> None:
        print(f"[server.py] Handler::OnDisconnect (connection={connection}, graceful={graceful})")

    def OnMessage(self, message: interceptor.MessageIn) -> bool:
        # message.Acknowledge()
        return False

    # @interceptor.path_handler("TEST")
    # def test_handler(self, message: interceptor.MessageIn) -> None:
    #     print("test_handler")
    #     message.Acknowledge()


class SubHandler(Handler):

    def __init__(self) -> None:
        super().__init__()

    @interceptor.path_handler("MY_PATH")
    def my_path_handler(self, message: interceptor.MessageIn) -> None:
        """
        This will trigger xyz, and give you some info along with a couple of images.

        Args:
            payload (list):
                A list containing:
                - 0 (json):
                    {
                        "key" (int): Some identifier.
                        "other_key" (str): Some string value.
                        "<some_id>" (int): Dynamic ID key.
                    }.

        Returns:
            payload (list):
                A list containing:
                - 0 (json): A JSON object with the following structure:
                    {...}
                - 1-4 (bytes): Binary JPG images.
        """
        print("SubHandler::test_handler2")
        message.Acknowledge()

    @interceptor.path_handler("TEST")
    def test_handler(self, message: interceptor.MessageIn) -> None:
        """Test if we get a response.

        Returns:
            None

        """
        print("SubHandler::test_handler")
        message.Acknowledge()


print(interceptor.inspect_path_handlers(SubHandler))


print("[server.py] Creating server")
handler = Handler()
server = interceptor.Server(2048, handler)
# server = interceptor.Server(2048, Handler())

print("[server.py] Starting server")
server.run(blocking=True)


print("[server.py] Continue in python")
import time

for i in range(5):
    time.sleep(2)
    # print("[server.py] Run one handler")
    server.run_one_pending_handler()
    # print("[server.py] Run one handler done")

# del server
# print("Server deleted")

print("[server.py] Stopping server")
server.stop(True)
print("[server.py] Stopped")

print("[server.py] Run one handler")
server.run_one_pending_handler()
print("[server.py] Handler done")

time.sleep(10)

print("[server.py] Starting server again")
server.run(blocking=True)
