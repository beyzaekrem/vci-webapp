import asyncio
import json
import os
from pathlib import Path

import pexpect

from .exceptions import PowerControlException

try:
    from .secret import *  # saves the power delivery units ssh password in environment  # noqa: F403
except ImportError:
    print("Warning: secret.py not found. Power control may not work as expected.")
    # Module does not exist, continue without importing
from .system_layout_reader import SystemLayoutReader


class PowerControl:
    def __init__(self, power_socket_json_path: Path | str = "config/power_sockets.json") -> None:
        self.path = power_socket_json_path
        with Path(self.path).open() as f:
            self.power_sockets: dict = json.load(f)

    def get_PDUs_with_type(self, device_type: str) -> list[dict]:  # noqa: N802
        """returns list of Power Device Units where device_type matches."""
        return [
            PDU
            for PDU in self.power_sockets.values()
            if isinstance(PDU, dict) and PDU.get("device_type") == device_type
        ]

    async def light_power(
        self,
        command: str,
    ) -> None:  # commands: "Off", "On", "Off 10 s", "Off 30 s", "Off 60 s"

        light_PDUs = self.get_PDUs_with_type("lights")  # noqa: N806
        tasks = [self._switch_sockets(PDU.get("ip"), PDU.get("sockets"), command) for PDU in light_PDUs]
        await asyncio.gather(*tasks)

    async def server_power(self, server_list: list[int], command: str) -> None:
        lr = SystemLayoutReader()
        server_names_to_power = [lr.get_server_name(s_id) for s_id in server_list]
        host_socket_pairs = []
        for PDU in self.get_PDUs_with_type("servers"):  # noqa: N806
            selected_sockets = []
            # select sockets that effect the selected server_list.
            for socket_desc, powered_devices in PDU.get("sockets").items():
                servers = [device for device in powered_devices if "vci" in device]
                for server in servers:
                    if server in server_names_to_power:
                        selected_sockets.append(socket_desc)  # noqa: PERF401
            host_socket_pairs.append((PDU.get("ip"), selected_sockets))

        tasks = [self._switch_sockets(ip, selected_sockets, command) for ip, selected_sockets in host_socket_pairs]
        await asyncio.gather(*tasks)

    async def camera_power(
        self, server_list: list[int], command: str, camera_ids=None
    ) -> None:  # commands: "Off", "On", "Off 10 s", "Off 30 s", "Off 60 s"
        # switch camera power to all cameras of server_id
        if any(sid in [1, 2, 3, 7] for sid in server_list):
            print("You need to reboot servers 1 2 3 and 7 together")

        socket_pair_per_server_id = []
        for server_id in server_list:
            socket_pairs = self._get_pdu_socket_pair(server_id, camera_ids)
            if socket_pairs is not None:
                socket_pair_per_server_id.extend(socket_pairs)
        print(socket_pair_per_server_id)
        minimized_socket_pairs = {ip: {} for ip in set([ip for ip, _ in socket_pair_per_server_id])}
        for ip, sockets in socket_pair_per_server_id:
            for socket in sockets:
                minimized_socket_pairs[ip].update(socket)

        tasks = [self._switch_sockets(pdu_ip, sockets, command) for pdu_ip, sockets in minimized_socket_pairs.items()]
        await asyncio.gather(*tasks)

    def _get_pdu_socket_pair(self, server_id: int, camera_ids=None) -> list:
        lr = SystemLayoutReader()

        camera_ids_of_server = lr.expected_cameras([lr.get_server_name(server_id)])
        if camera_ids is not None:
            camera_ids_of_server = [cam_id for cam_id in camera_ids_of_server if cam_id in camera_ids]
            if len(camera_ids_of_server) == 0:
                return None
        host_socket_pairs = []

        # some sockets unfortunately power multiple cameras that are connected to different servers.
        # If we power the socket down and up we need to restart all affected servers.
        effected_servers = []
        found_camera_ids = []

        for PDU in self.get_PDUs_with_type("cameras"):
            selected_sockets = []
            for socket_desc, powered_cameras in PDU.get("sockets").items():
                if any(cam_id in powered_cameras for cam_id in camera_ids_of_server):
                    selected_sockets.append({socket_desc: powered_cameras})
                    effected_servers.extend([device for device in powered_cameras if "vci" in device])
                    found_camera_ids.extend([device for device in powered_cameras if device in camera_ids_of_server])

            host_socket_pairs.append((PDU.get("ip"), selected_sockets))
        effected_servers = list(set(effected_servers))

        if "vci-" + str(server_id).zfill(2) not in effected_servers:
            msg = f"Selected sockets do not effect the server_id {server_id}. Maybe power_sockets.json is outdated?"
            raise PowerControlException(msg)
        if set(found_camera_ids) != set(camera_ids_of_server):
            print(
                f"Warning! Could not find power sockets of {'vci-' + str(server_id).zfill(2)} cameras {set(camera_ids_of_server) - set(found_camera_ids)} "
            )
        return host_socket_pairs

    @staticmethod
    async def _switch_sockets(
        pdu_ip: str, sockets: dict | list, command: str, *, debug_only: bool = False
    ) -> None:  # pdu is power delivery unit,
        if isinstance(sockets, list):
            sockets = {s: [s] for s in sockets}  # convert list to dict
        if len(sockets) == 0:
            return
        ssh_command = f"ssh ximea@{pdu_ip}"
        print(f"power {pdu_ip}. Toggle sockets {list(sockets)}")
        if debug_only:
            print("set_debug_only: No changes to power socket.")
            return
        child = pexpect.spawn(ssh_command, encoding="utf-8", timeout=10)
        child.expect("Password:")
        password = os.environ["PDU_PASSWORD"]
        if password is None:
            print(f"Please provide password for ximea@{pdu_ip} in environment variable 'PDU_PASSWORD'")
        child.sendline(password)

        # Navigate through the menu
        child.expect("Main Menu")
        child.sendline("4")  # 4  Console Commands

        child.expect("Console Commands")
        child.sendline("")  # 1  Command (by DescName)
        child.expect("Enter Command:")

        previous_command = ""

        for cnt, socket_desc in enumerate(sockets.keys(), start=1):
            connected_devices = sockets[socket_desc]
            # Send the command to switch off the socket
            [child.send("\x08") for _ in range(len(previous_command))]
            full_command = f"2.{socket_desc}:{command}"
            child.sendline(full_command)
            previous_command = full_command
            await asyncio.sleep(1)
            child.sendline("")
            index = child.expect(
                [
                    f"Device 2.Output '{socket_desc}' switched to '{command}'",
                    pexpect.EOF,
                    pexpect.TIMEOUT,
                ]
            )
            if index != 0:
                print(child.before)
                raise PowerControlException(
                    f"setting power '{socket_desc}':{command}  {pdu_ip} {connected_devices} failed. {child.before}"
                )
            print(f"power '{socket_desc}':{command}  {pdu_ip} {connected_devices} succeeded ({cnt}/{len(sockets)})")


POWER_CONTROL = PowerControl()
