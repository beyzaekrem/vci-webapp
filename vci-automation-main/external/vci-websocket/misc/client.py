import time

import interceptor

client = interceptor.Client("127.0.0.1", 2048)
client.run(blocking=False)

client.wait_for_connection(200)
print("Wait done")

if client.is_connected():
    print("Connected")
else:
    print("Not connected")
    # exit now
    exit(0)

# start_t = time.time()
# for i in range(1):
#     promise = client.async_send(interceptor.MessageOut("TEST_PATH"))
#     reply = promise.wait_for(1000)
#     if not reply:
#         print("Didn't get a reply")
# end_t = time.time()
# print(f"Total time: {end_t - start_t} s")

promises: list[interceptor.MessagePromise] = []
message = interceptor.MessageOut("TEST")
start_t = time.time()
# for i in range(80000):
for i in range(8):
    promises.append(client.async_send(message))

for promise in promises:
    response = promise.wait()
    if not response:
        print("Didn't get a reply")
    elif response.is_error():
        print("Got error:", response.error)
    else:
        print("Got reply")
    # print("Got reply")
end_t = time.time()
print(f"Total time: {end_t - start_t} s")


interface = client.async_send(interceptor.MessageOut("INTERFACE")).wait().payload[0].ToPyObject()

for key, value in interface.items():
    print(key, ":", value)
