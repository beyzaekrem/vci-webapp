### Server Messages

All capture servers run the sparrow server from the (vci-capture repository)[https://gitlab.informatik.uni-bonn.de/vci-dev/vci-capture]. The connection and communication runs via (vci-websocket)[https://gitlab.informatik.uni-bonn.de/vci-dev/vci-websocket].

We create and send Messages that contain a Path (str) and and optional Payload (dict). The Server response is another Message.
The valid Paths that we can send messages to are called API endpoints. (API meaning Application Programming Interface)

The endpoints are wrapped by vci-automation. You can also send and arbitrary message:

```python
from controller import Controller, trigger_box

with Controller() as c:
    c.send("STATUS")
```
### Server Modes

Since the vci-capture servers use camera hardware and are capable of performing long tasks like capturing to disk, they are statefull.

The server mode is the highest-level state the server has. 
it determines which API endpoints are available and the server may give you different responses to the same endpoint depending on the mode.

Some endpoints are always available. For example, you can always request get_status, get_camera_info and switch_mode.

Modes:

- "single"