# ruff: noqa: S311, F811, S101, T201

import contextlib
import os
import random
import threading
import time

import pytest

import interceptor


class TestConnection:

    def test_connection_success(self) -> None:
        """
        Test a basic client-server connection.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_simple_dialog(self) -> None:
        """
        Test a basic message exchange between client and server.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        promise = client.async_send(interceptor.MessageOut("Simple"))
        reply = promise.wait_for(1)
        expected_response = "Hello from server"
        assert reply.payload[0].ToString() == expected_response
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_short_dialog(self) -> None:
        """
        Tests a basic message exchange. Doens't use lists of payloads but just a plain payload
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        message = "Hello from client"
        payload = interceptor.Payload.FromString(message)
        promise = client.async_send(interceptor.MessageOut("ShortAck", payload))
        reply = promise.wait_for(1)
        expected_response = "Hello from server"
        assert reply.payload[0].ToString() == expected_response
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_reconnect(self) -> None:
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        client.async_send(interceptor.MessageOut("Simple"), send_and_forget=True)
        server_thread.join()
        assert not server_thread.is_alive()
        with pytest.raises(interceptor.NotConnectedError):
            client.async_send(interceptor.MessageOut("Simple"), send_and_forget=True)
        # assert not client.is_connected()  # noqa: ERA001
        server_thread = TestServer.create_server()
        time.sleep(2)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        # client.async_send(interceptor.MessageOut("Simple"), send_and_forget=True)  # noqa: ERA001
        server_thread.join()
        assert not server_thread.is_alive()


class TestHandlers:

    def test_ambiguous_handlers(self) -> None:
        """
        Test that defining multiple ambiguous handlers for the same path works as intended.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        promise = client.async_send(interceptor.MessageOut("ambiguous"))

        reply = promise.wait_for(1)
        # ah11 = first mention of Path and function
        # ah12 = same Path name, same function name (defined after ah11)
        # ah21 = same path name, other function name (defined after ah11, ah12)
        # ah22 = other path name, same function name (defined after ah11, ah12, ah21)
        assert reply.payload[0].ToString() == "ah21"
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_wrong_path(self) -> None:
        """
        Test that an invalid message path raises PathDoesNotExistError.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        promise = client.async_send(interceptor.MessageOut("DoesntExists"))
        with pytest.raises(interceptor.PathDoesNotExistError):
            promise.wait_for(1)
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_path_overwrite(self) -> None:
        """
        Test that overwriting works. The function of path "ow1" is changed to path "ow2".
        -ow1 no longer has any handler-function associated with.
        -ow2 should use the function originally defined for ow1
        -ow3 has two functions and should throw a PathAlreadyDefinedError
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        # This handler function got overwritten by path "ow2"
        promise = client.async_send(interceptor.MessageOut("ow1"))
        with pytest.raises(interceptor.PathDoesNotExistError):
            reply = promise.wait_for(1)

        # The overwriting function for ow2 returns "allgood" while the overwritten function returns "error"
        expected_response = "all good"
        promise = client.async_send(interceptor.MessageOut("ow2"))
        reply = promise.wait_for(1)
        assert reply.payload[0].ToString() == expected_response
        server_thread.join(10)
        assert not server_thread.is_alive()


class TestClient:

    def test_client_stati(self) -> None:
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)

    def test_ack_empty_answer(self) -> None:
        """
        Test that a message expecting only an acknowledgment returns a valid (non-null) reply.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        promise = client.async_send(interceptor.MessageOut("OnlyAck"))
        reply = promise.wait_for(1)
        assert reply
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_no_ack(self) -> None:
        """
        Test that sending a message without acknowledgment raises MissingAcknowledgeError.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        promise = client.async_send(interceptor.MessageOut("NoAck"))
        with pytest.raises(interceptor.MissingAcknowledgeError):
            promise.wait_for(1)
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_connection_no_server(self) -> None:
        """
        Test that connecting without a running server raises NotConnectedError.
        """
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        with pytest.raises(interceptor.NotConnectedError):
            client.wait_for_connection(0.2)
        assert not client.is_connected()

    def test_multiple_messages(self, number_of_messages: int = 10) -> None:
        """
        Test sending multiple messages in parallel and receiving correct replies for each.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        messages_out = {}
        payloads_out = {}
        promises: list[interceptor.MessagePromise] = {}
        replies = {}
        for i in range(number_of_messages):
            messages_out[i] = {"msg_number": i}
            payloads_out[i] = interceptor.Payload.FromDict(messages_out[i])
            promises[i] = client.async_send(interceptor.MessageOut("Echo", [payloads_out[i]]))

        for i in range(number_of_messages):
            replies[i] = promises[i].wait_for(1).payload[0].ToDict()
            print(replies[i])
            assert replies[i]["msg_number"] == i

        assert replies.__len__() == number_of_messages
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_multiple_messages_random(self, number_of_messages: int = 10) -> None:
        """
        Test that multiple messages with random reply delays are matched to correct requests.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        messages_out = {}
        payloads_out = {}
        promises: list[interceptor.MessagePromise] = {}
        replies = {}
        for i in range(number_of_messages):
            messages_out[i] = {"msg_number": i}
            payloads_out[i] = interceptor.Payload.FromDict(messages_out[i])
            promises[i] = client.async_send(interceptor.MessageOut("EchoRandom", [payloads_out[i]]))

        for i in range(number_of_messages):
            replies[i] = promises[i].wait_for(1).payload[0].ToDict()
            print(replies[i])
            assert replies[i]["msg_number"] == i

        assert replies.__len__() == number_of_messages
        server_thread.join(10)
        assert not server_thread.is_alive()

    def WIP_test_wait_timings(self, wait_time_in_seconds: float = 0.27, number_of_trials: float = 20) -> None:
        """
        Tests the correctness of "wait_for" function.
        """
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)

        longest_wait_time_connection = 0
        shortest_wait_time_connection = float("inf")
        for _ in range(number_of_trials):
            start_time_connection = time.perf_counter()
            with contextlib.suppress(Exception):
                client.wait_for_connection(wait_time_in_seconds)
            end_time_connection = time.perf_counter()
            total_time_connection = end_time_connection - start_time_connection
            longest_wait_time_connection = max(longest_wait_time_connection, total_time_connection)
            shortest_wait_time_connection = max(shortest_wait_time_connection, total_time_connection)
        overtime_max_ratio = longest_wait_time_connection / wait_time_in_seconds
        overtime_min_max_ration = longest_wait_time_connection / shortest_wait_time_connection

        acceptable_interval = (0.99, 1.01)
        assert overtime_max_ratio < acceptable_interval[1]
        assert overtime_min_max_ration > acceptable_interval[0]
        print(overtime_max_ratio)
        print(overtime_min_max_ration)


class TestPayloads:
    def test_string_payloads(self) -> None:
        """
        Test function for payload handling of Strings.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        message_string = "Espresso"
        payload_string = interceptor.Payload.FromString(message_string)
        promise = client.async_send(interceptor.MessageOut("String", [payload_string]))
        reply = promise.wait_for(1)
        expected_string = "Espresso Macchiato"
        reply_string = reply.payload[0].ToString()
        assert reply_string == expected_string
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_dict_payloads(self) -> None:
        """
        Test function for payload handling of dicts
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        message_dict = {"first": "Espresso"}
        payload_dict = interceptor.Payload.FromDict(message_dict)
        promise = client.async_send(interceptor.MessageOut("Dict", [payload_dict]))
        reply = promise.wait_for(1)
        expected_dict = {"first": "Espresso", "second": "Macchiato"}
        reply_dict = reply.payload[0].ToDict()
        assert reply_dict == expected_dict
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_multiple_payloads(self, num_payloads: int = 10) -> None:
        """
        Tests handling of multiple payloads.
        """
        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()
        payloads: list[interceptor.Payload] = []
        for i in range(num_payloads):
            message = str(i)
            payloads.append(interceptor.Payload.FromString(message))
        promise = client.async_send(interceptor.MessageOut("Echo", payloads))
        reply = promise.wait_for(1)
        reply_payloads = reply.payload
        for i, reply_payload in enumerate(reply_payloads):
            assert reply_payload.ToString() == payloads[i].ToString()
        server_thread.join(10)
        assert not server_thread.is_alive()

    def test_large_payloads(self, size_payload_in_bytes: int = int(10e7)) -> None:
        noise_payload_bytes = os.urandom(size_payload_in_bytes)

        server_thread = TestServer.create_server()
        time.sleep(2)
        client = interceptor.Client("127.0.0.1", 2048)
        client.run(blocking=False)
        client.wait_for_connection(0.2)
        assert client.is_connected()

        payload = interceptor.Payload.WrapPyBytes(noise_payload_bytes)

        promise = client.async_send(interceptor.MessageOut("Echo", [payload]))
        reply = promise.wait_for(10)
        recieved_payload = reply.payload[0].PyMemoryView()
        recieved_payload.tobytes()

        assert len(recieved_payload) == len(noise_payload_bytes)
        accepted_discrepancies = size_payload_in_bytes * 0.01
        discrepancies = sum(x != y for x, y in zip(recieved_payload, noise_payload_bytes))
        assert discrepancies / size_payload_in_bytes <= accepted_discrepancies
        server_thread.join()
        assert not server_thread.is_alive()


class TestServer:
    # Server thread functions
    @staticmethod
    def start_test_server(port: int) -> None:
        server = interceptor.Server(port, SubHandlerTestClass())
        server.run(blocking=False)
        assert server.is_running()
        for _ in range(50):
            time.sleep(0.1)
            server.run_one_pending_handler()
        server.stop(run_pending_handlers=True)
        assert not server.is_running()

    @staticmethod
    def create_server(port: int = 2048) -> threading.Thread:
        server_thread = threading.Thread(target=TestServer.start_test_server, args=(port,))
        server_thread.start()
        return server_thread

    @staticmethod
    def server_test_set_handler(port: int) -> None:
        server = interceptor.Server(port, SubHandlerTestClass())
        server.run(blocking=False)
        assert server.is_running()
        for _ in range(10):
            time.sleep(0.1)
            server.run_one_pending_handler()
        server.set_handler(SubHandlerAlternativeClass())
        assert server.is_running()
        for _ in range(10):
            time.sleep(0.1)
            server.run_one_pending_handler()
        server.stop(run_pending_handlers=True)
        assert not server.is_running()

    @staticmethod
    @pytest.mark.filterwarnings("error")
    def test_create_set_handler(port: int = 2048) -> None:
        server_thread = threading.Thread(target=TestServer.server_test_set_handler, args=(port,))
        server_thread.start()
        server_thread.join()
        assert not server_thread.is_alive()


class SubHandlerTestClass(interceptor.MessageHandler):

    @interceptor.path_handler("OnlyAck")
    def only_ack_1(self, message: interceptor.MessageIn) -> None:
        """
        Only send an empy acknowledge
        """
        message.Acknowledge()

    @interceptor.path_handler("Simple")
    def simple_answer(self, message: interceptor.MessageIn) -> None:
        """
        Send a short hello message as acknowledge
        """
        response = "Hello from server"
        payload = interceptor.Payload.FromString(response)
        message.Acknowledge([payload])

    @interceptor.path_handler("ShortAck")
    def short_answer(self, message: interceptor.MessageIn) -> None:
        """
        Sends a short payload back. (not a list of payloads)
        """
        assert message.payload[0].ToString() == "Hello from client"
        response = "Hello from server"
        payload = interceptor.Payload.FromString(response)
        message.Acknowledge(payload=payload)

    @interceptor.path_handler("NoAck")
    def noack_handler(self, message: interceptor.MessageIn) -> None:
        """
        Don't do anything (no acknowledge)
        """

    @interceptor.path_handler("Echo")
    def echo_handler(self, message: interceptor.MessageIn) -> None:
        """
        Echo the incoming message (send incoming payload back as acknowledge)
        """
        message.Acknowledge(message.payload)

    @interceptor.path_handler("String")
    def string_handler(self, message: interceptor.MessageIn) -> None:
        """
        Add a " Macchiato" to the incoming String payload and send it back via acknowledge
        """
        payload_string = message.payload[0].ToString()
        payload_string += " Macchiato"
        new_payload = interceptor.Payload.FromString(payload_string)
        message.Acknowledge(new_payload)

    @interceptor.path_handler("Dict")
    def dict_handler(self, message: interceptor.MessageIn) -> None:
        """
        Add a "second":"Macchiato" to the incoming Dict payload and send it back via acknowledge
        """
        payload_dict = message.payload[0].ToDict()
        payload_dict["second"] = "Macchiato"
        new_payload = interceptor.Payload.FromDict(payload_dict)
        message.Acknowledge(new_payload)

    @interceptor.path_handler("EchoRandom")
    def echo_random_handler(self, message: interceptor.MessageIn) -> None:
        """
        Echo the incoming message (send incoming payload back as acknowledge)
        after a short random delay between 0 and 0.5 seconds
        """
        random_wait = random.uniform(0, 0.5)
        time.sleep(random_wait)
        message.Acknowledge(message.payload)

    @interceptor.path_handler("ow1")
    def ow_handler(self, message: interceptor.MessageIn) -> None:
        """
        Used to test overwriting of functions. This function should never be called because it should be overwritten
        """
        should_have_been_overwritten = interceptor.Payload.FromString("This should have been overwritten")
        message.Acknowledge([should_have_been_overwritten])

    @interceptor.path_handler("ow2")
    def ow_handler(self, message: interceptor.MessageIn) -> None:
        """
        This function was already defined for another path (ow1). It is used to test overwriting of functions
        """
        should_not_have_been_overwritten = interceptor.Payload.FromString("all good")
        message.Acknowledge([should_not_have_been_overwritten])

    @interceptor.path_handler("ambiguous")
    def ambiguous_handler_1(self, message: interceptor.MessageIn) -> None:
        """
        All these functions were used for testing overwriting of paths, and functions.
        Depricated since PathAlreadyDefinedError exists now
        """
        payload = interceptor.Payload.FromString("ah11")
        message.Acknowledge([payload])

    @interceptor.path_handler("ambiguous")
    def ambiguous_handler_1(self, message: interceptor.MessageIn) -> None:
        """
        All these functions were used for testing overwriting of paths, and functions.
        Depricated since PathAlreadyDefinedError exists now
        """
        payload = interceptor.Payload.FromString("ah12")
        message.Acknowledge([payload])

    @interceptor.path_handler("ambiguous")
    def ambiguous_handler_2(self, message: interceptor.MessageIn) -> None:
        """
        All these functions were used for testing overwriting of paths, and functions.
        Depricated since PathAlreadyDefinedError exists now
        """
        payload = interceptor.Payload.FromString("ah21")
        message.Acknowledge([payload])

    @interceptor.path_handler("ambiguous2")
    def ambiguous_handler_1(self, message: interceptor.MessageIn) -> None:
        """
        All these functions were used for testing overwriting of paths, and functions.
        Depricated since PathAlreadyDefinedError exists now
        """
        payload = interceptor.Payload.FromString("ah22")
        message.Acknowledge([payload])


class SubHandlerAlternativeClass(interceptor.MessageHandler):
    @interceptor.path_handler("Simple")
    def simple_answer(self, message: interceptor.MessageIn) -> None:
        """
        Send a short holla message as acknowledge
        """
        response = "Holla from server"
        payload = interceptor.Payload.FromString(response)
        message.Acknowledge([payload])


with pytest.raises(interceptor.PathAlreadyDefinedError):

    class TestOverwriteSubhandlerClass(interceptor.MessageHandler):
        @interceptor.path_handler("ow3")
        def ow_handler_1(self, message: interceptor.MessageIn) -> None:
            fcnt_number = interceptor.Payload.FromString("1")
            message.Acknowledge([fcnt_number])

        @interceptor.path_handler("ow3")
        def ow_handler_2(self, message: interceptor.MessageIn) -> None:
            fcnt_number = interceptor.Payload.FromString("2")
            message.Acknowledge([fcnt_number])
