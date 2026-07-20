import argparse

from natsort import natsorted

from controller import Controller, argmods
import interceptor
import pprint
from datetime import datetime


def send_and_print(client, path, payload=None, timeout=3000):
    """
    Helper function: send a message and print response or error.
    """
    print(f"\n=== Sending {path} ===")
    message = interceptor.MessageOut(path)
    print(type(payload))
    if payload:
        if type(payload) is dict:
            message = interceptor.MessageOut(path, payload=interceptor.Payload.FromDict(payload))
        else:
            message = interceptor.MessageOut(path, payload=interceptor.Payload.FromString(payload))
    promise = client.async_send(message)
    reply = promise.wait_for(timeout)

    if not reply:
        print(f"[{path}] No reply (timeout)")
        return
    if reply.is_error():
        print(f"[{path}] Error: {reply.error}")
        # return

    print(f"[{path}] Success")
    try:
        print("Payload Dict:")
        if reply.payload is not []:
            pprint.pprint(reply.payload[0].ToDict())
    except Exception as e:
        print(f"[{path}] (no JSON payload) {e}")

# to add all cameras, for setting up database
def add_all_cameras(client) -> list:
    cameras = ['C0000', 'C0001', 'C0004', 'C0003', 'C0005', 'C0006', 'C0007', 'C0008', 'C0009', 'C0010', 'C0012', 'C0013', 'C0014', 'C0016', 'C0018', 'C0019', 'C0020', 'C0021', 'C0022', 'C0024', 'C0025', 'C0026', 'C0028', 'C0029', 'C0030', 'C0031', 'C0034', 'C0038', 'C0037', 'C0039', 'C1000', 'C1001', 'C1002', 'C1004', 'C1005', 'D003L', 'D005Z', 'M0001', 'M0003', 'M0005', 'M0007', 'M0006', 'M0008', 'M0009', 'M0010', 'M0011', 'M0013', 'M0014', 'M0015', 'M0016', 'M0017', 'M0018', 'M0019', 'M0021', 'M0022', 'M0023', 'M0024']
    for i in range(len(cameras)):
        send_and_print(client, "ADD_CAMERA", {"camera_id":cameras[i]})


def add_servers_to_db(client, servers: dict) -> None:
    # every sever is a key, list is cameras

    # hier ist das problem, ich weiß noch nicht wie servers aussieht, es übergibt den eintrag der liste als namen
    #print(servers)
    server_names = list(servers.keys())
    print(server_names)
    for server in server_names:
        print("name: " + server)
        print("cameras: " + str(list(set(servers[server]))))
        send_and_print(client, "ADD_SERVER", {"name":server, "cameras":list(set(servers[server]))})


def main():
    print("[strapi client] Starting...")
    client = interceptor.Client("localhost", 2443) 
    client.run(blocking=False)
    client.wait_for_connection(200)

    if not client.is_connected():
        print("Not connected to server")
        return

    print("Connected to strapi interceptor server")
    send_and_print(client, "CLEAN_CACHES") 
    add_all_cameras(client)


    parser = argparse.ArgumentParser(description="Get info about a recording and place it into the database")
    argmods.add_server_list_argument(parser)  # optional filter by server_index

    argmods.add_capture_name_argument(parser, default="")  # optional filter by name

    args = parser.parse_args()
    search_key = args.capture_name

    list_of_captures_to_add = []

    with Controller(args.server) as c:  # connect to servers
        c.switch_mode("replay")  # the different modes on the servers have different functionality.
        # replay mode gives us all the info and control about recordings captured to server ssds

        servers = {}

        # not all recordings are actually on all servers, this is mostly due to tests or bugs.
        # go over all servers and compile the full list of recordings.
        available_recordings = []
        for server_index in range(len(c.servernames)):
            status = c.get_status(server_index, verbose=True)
            available_recordings.extend(status.get("available_recordings"))
            print(status["paths"])
            servers.update({c.servernames[server_index]: []})
        available_recordings = set(available_recordings)
        available_recordings = natsorted(list(available_recordings))

        # print the info about the recordings for each servers.
        for rec in available_recordings:
            if search_key in rec:  # optional filter by name
                # let the servers try to select the recording
                c.set_recording_name(rec, invalid_ok=True)

                cameras = []
                paths = []
                capture_time = ""
                frame_count = 0
                rec_info = None
                
                print(f"\n---{rec}----")
                for server_index in range(len(c.servernames)):
                    
                    # after recording name is selected on the server,
                    # the status changes to include recording info like frame length etc.

                    rec_info: dict = c.get_status(server_index, verbose=True)
                    print("rec info")
                    #print(rec_info)
                    if "available_recordings" in rec_info:
                        rec_info.pop("available_recordings")
                        print("rec info")
                        #print(rec_info)

                        # only print if the server has this recording
                        if rec_info["recording_name"] == rec:
                            print(f"{c.servernames[server_index]} --- {rec_info}")
                            servers[c.servernames[server_index]].extend(rec_info["camera_ids"])
                            cameras.extend(rec_info["camera_ids"])
                            capture_time = rec_info["capture_timestamp"]
                            frame_count = rec_info["frame_count"]
                            paths.extend(rec_info["paths"])
                    
                print(capture_time)

                caches = []
                calib = ""
                for path in list(set(paths)):
                    if path.split('_')[-1] == "calib.json":
                        calib = path

                    caches.append({
                        "path": path
                    })
                print("caches: " + str(caches))

                list_of_captures_to_add.append({
                    "capture_id": rec,
                    #"time": capture_time,
                    "cameras": natsorted(cameras),
                    "frame_count": frame_count,
                    "caches": caches,
                    "custom": "calib path: " + calib
                })
                if capture_time != '':
                    list_of_captures_to_add[-1].update({
                        "date": capture_time.split("T")[0],
                        "time": datetime.fromisoformat(capture_time).strftime("%H:%M:%S.%f")[:-3],
                    })
    
    #add_servers_to_db(client, servers)

    #print(list_of_captures_to_add)
    # add all captures
    for i in range(len(list_of_captures_to_add)):
        #print(list_of_captures_to_add[i]["capture_id"] + " " + list_of_captures_to_add[i]["time"])
        send_and_print(client, "ADD_CAPTURE", list_of_captures_to_add[i])


if __name__ == "__main__":
    main()