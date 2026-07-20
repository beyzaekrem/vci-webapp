# ruff: noqa: T201, INP001
import argparse
import asyncio
import subprocess

from natsort import natsorted

# region command
command_functions = {}


def command(path, pass_server_list=False, **options):
    def decorator(f):
        if path in command_functions:
            raise RuntimeError(f"path {path} is already implemented by function {command_functions[path]}")
        command_functions[path] = (f, pass_server_list)
        return f

    return decorator


async def run_command(path, server_list, **options):
    if path in command_functions:
        f, pass_server_list = command_functions[path]
        if pass_server_list:
            await f(server_list, **options)
        else:
            tasks = [f(server_id, **options) for server_id in server_list]
            await asyncio.gather(*tasks)
    else:
        raise NotImplementedError("No image save function defined for format", path)


# endregion


@command("echo")
async def run_git_echo(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh -v {host} 'cd vci-capture && \
    echo {host} is reachable'"
    for i in range(60):
        try:
            process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=1)
            _remember_result(host, process.returncode == 0)
            if process.returncode == 0:
                print(stdout.decode())
            else:
                print(f"{host} unreachable")
                print(stdout.decode())
            return
        except asyncio.TimeoutError:
            print(f"{host} unreachable (timeout). retry {i}...")
    _remember_result(host, success=False)


@command("log")
async def run_git_log(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f'ssh {host} \'cd vci-capture && \
    git log -1 --pretty=format:"  {host}: %h - %s (%cd)" && \
    echo "" && \
    echo "Submodule logs:" && \
    git submodule foreach "git log -1 --pretty=format:\\"  %h - %s (%cd)\\""\''

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    print(stdout.decode(), "\n")


@command("restore")
async def run_git_restore_file(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    file = "camera_ignore.json"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    git restore {file}'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    print(stdout.decode(), "\n")


@command("pull")
async def run_git_pull(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f'ssh {host} \'cd vci-capture && \
    git fetch && \
    git pull && \
    git log -1 --pretty=format:"  {host}: %h - %s (%cd)" && \
    echo "" && \
    git submodule update --remote && \
    echo "Submodule logs:" && \
    git submodule foreach "git log -1 --pretty=format:\\"  %h - %s (%cd)\\""\''

    await asyncio.sleep(server_id * 2)  # pulls spaced out otherwise gitlab closes all connection
    print(f"git pull {host}")
    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"Git pull on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"Git pull on {host} failed.")
        print(stderr.decode(), "\n")


@command("stash-pull")
async def run_git_stash_pull(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f'ssh {host} \'cd vci-capture && \
    git stash && \
    git fetch && \
    git pull && \
    git log -1 --pretty=format:"  {host}: %h - %s (%cd)" && \
    echo "" && \
    git submodule update --remote && \
    echo "Submodule logs:" && \
    git submodule foreach "git log -1 --pretty=format:\\"  %h - %s (%cd)\\"" && \
    echo "" && \
    echo "Stash list:" && \
    git stash list\''

    await asyncio.sleep(server_id * 2)  # space out pulls so GitLab doesn’t cut connections
    print(f"git stash && git pull {host}")
    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"Git stash+pull on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"Git stash+pull on {host} failed.")
        print(stderr.decode(), "\n")


@command("checkout-main")
async def checkout(
    server_id: int, branch: str = "main", submodule_branch_or_commit: str = "main"
) -> None:  # last_deploy:  branch deploy,  submodule cb65834
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"""ssh {host} 'cd vci-capture && \
    git stash && \
    git fetch && \
    git checkout {branch} && \
    git pull origin {branch}&& \
    echo "Checked out and pulled {branch} on {host}" && \
    git log -1 --pretty=format:"  {host}: %h - %s (%cd)" && \
    echo "" && \
    git submodule update --init && \
    echo "Checking out submodule to {submodule_branch_or_commit}..." && \
    cd external/vci-websocket && \
    git fetch && \
    git checkout {submodule_branch_or_commit} && \
    echo "Submodule logs:" && \
    git log -1 --pretty=format:"  %h - %s (%cd)"'
    """

    await asyncio.sleep(server_id * 2)  # Delay to avoid overloading the Git server
    print(f"Checking out and pulling commit {branch} on {host}")
    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"Checkout and pull on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"Checkout and pull on {host} failed.")
        print(stderr.decode(), "\n")


@command("checkout-dev")
async def checkout_development(server_id: int) -> None:
    await checkout(server_id, branch="development", submodule_branch_or_commit="main")


@command("orbbec")  # unpizs a folder into /opt/. Then renames the unziped folder
async def unzip_to_opt(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    sudo unzip OrbbecSDK.zip -d /opt/ && \
    cd /opt/ && \
    sudo mv OrbbecSDK_v2.4.11_202508040936_058db73_linux_x86_64/ OrbbecSDK'"

    await asyncio.sleep(server_id * 2)  # space out pulls so GitLab doesn’t cut connections
    print(f"OrbbecSDK unzip and rename {host}")
    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"OrbbecSDK unzip and rename on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"OrbbecSDK unzip and rename on {host} failed.")
        print(stderr.decode(), "\n")


@command("reset", pass_server_list=True)
async def reset(server_list: int) -> None:
    from controller import Controller

    c = Controller(server_list)
    c.hard_reset()


@command("build")
async def run_docker_build(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    docker compose down && \
    docker compose build && \
    docker compose up -d'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"docker compose down, build, up on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"docker compose down, build, up on {host} failed.")
        print(stderr.decode(), "\n")


@command("down")
async def run_docker_down(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    docker compose down && \
    docker ps'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"docker compose down on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"docker compose down on {host} failed.")
        print(stderr.decode(), "\n")


@command("up")
async def run_docker_up(server_id: int) -> None:
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    docker compose up -d && \
    docker ps'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        print(f"docker compose up on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        print(f"docker compose up on {host} failed.")
        print(stderr.decode(), "\n")


@command("run")
async def run_docker_exec(server_id):
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    (docker compose exec vci_capture_development /bin/bash -c ./run.sh | head -n 5; nohup docker compose exec vci_capture_development /bin/bash -c ./run.sh >/dev/null 2>&1 &) '"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = await process.communicate()

    # Print the first few lines of output
    output_lines = stdout.decode().strip().split("\n")
    for line in output_lines[:5]:  # Limit to first 5 lines
        print(f"{host}: {line}")

    print(f"Started docker compose exec on {host} in the background.")


@command("cameras")
async def check_cameras(server_id):
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'cd vci-capture && \
    docker compose exec vci_capture_development python scripts/check_cameras.py'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    _remember_result(host, process.returncode == 0)
    if process.returncode == 0:
        log = stdout.decode()
        found_cameras = log[log.find("Cameras found:") :].rstrip()
        _remember_result(host, True, found_cameras.replace("MFFFF", "-----"))
        print(f"check cameras on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        _remember_result(host, False)
        print(f"check cameras on {host} failed.")
        print(stderr.decode(), "\n")


@command("reboot", True)
async def reboot_server_and_cameras(server_list):

    tasks = [run_docker_down(s_id) for s_id in server_list]
    await asyncio.gather(*tasks)
    await asyncio.sleep(3)
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.camera_power(server_list, "Off")
    # wait a little so stored energy in the power supply of the camera runs out
    await asyncio.sleep(10)
    # turn cameras back on
    await POWER_CONTROL.camera_power(server_list, "On")

    await asyncio.sleep(5)

    tasks = [
        reboot_server(server_id) for server_id in server_list
    ]  # it takes ~50 seconds to reboot the server, however the PCI connection is enabled fairly early
    await asyncio.gather(*tasks)


@command("reboot_server")
async def reboot_server(server_id):
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'sudo reboot'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if "closed by remote host" in stderr.decode():
        _remember_result(host, True)
        print(f"sudo reboot on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        _remember_result(host, False)
        print(f"sudo reboot on {host} failed.")
        print(stderr.decode(), "\n")


@command("shutdown_server")
async def shutdown_server(server_id):
    host = f"vci-capture-{str(server_id).zfill(2)}"

    ssh_command = f"ssh {host} 'sudo shutdown now'"

    process = await asyncio.create_subprocess_shell(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if "closed by remote host" in stderr.decode():
        _remember_result(host, True)
        print(f"sudo shutdown now on {host} succeeded.")
        print(stdout.decode(), "\n")
    else:
        _remember_result(host, False)
        print(f"sudo shutdown now on {host} failed.")
        print(stderr.decode(), "\n")


@command("server_off", True)
async def server_off(server_list):
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.server_power(server_list, "Off")


@command("server_on", True)
async def server_on(server_list):
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.server_power(server_list, "On")


@command("cameras_off", True)
async def cameras_off(server_list, camera_ids=None):
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.camera_power(server_list, "Off", camera_ids)


@command("cameras_on", True)
async def cameras_on(server_list, camera_ids=None):
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.camera_power(server_list, "On", camera_ids)


@command("lights_off", True)
async def lights_off(server_list) -> None:
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.light_power("Off")


@command("lights_on", True)
async def lights_on(server_list) -> None:
    from controller.power_control import POWER_CONTROL

    await POWER_CONTROL.light_power("On")


# region result summary
results = {}  # dictionary to store success/failure per server


def _remember_result(host, success, optional_text=None):
    if success:
        results[host] = "✅  Success "
    else:
        results[host] = "❌  Failed "
    if optional_text is not None:
        results[host] += f" --- {optional_text}"


def _print_results():
    if len(results) > 0:
        print(f"\n=== Summary ({len(results)} servers) ===")
        for host in natsorted(results.keys()):
            print(f"{host}: {results[host]}")


# endregion
async def main() -> None:
    parser = argparse.ArgumentParser(description="vci-capture ssh commands for git and docker compose")
    parser.add_argument("command", type=str, choices=list(command_functions.keys()))
    parser.add_argument("-s", "--server", nargs="+", type=int, default=-1)
    parser.add_argument("--camera_ids", nargs="+", default=None)
    parser.add_argument("--something_else", nargs="+", default=None)

    args = parser.parse_args()
    server_list = (
        args.server if args.server != -1 else range(1, 16)
    )  # cant just be None here. Should resolve from system_layout.json

    print(f"\nvci-capture --- {args.command} {server_list}\n")

    c = args.command
    options = vars(args)  # turns parsed arguments into a dictionary
    options.pop("command")
    options.pop("server")
    options = {k: v for k, v in options.items() if v is not None}  # remove None values

    await run_command(c, server_list, **options)

    _print_results()


if __name__ == "__main__":
    asyncio.run(main())
