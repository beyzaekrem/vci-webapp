# VCI-Webapp

The vci-webapp is located in the highest abstraction layer of the capture architecture.
It's purpose is to provide a Web GUI interface.
Features:

- Viewing livestreams of cameras in the VCI
- Reading and setting camera parameters
- UI for calibrating and capturing

## How To

### Use the Webapp

Open the webapp in your browser [here](http://10.3.10.20/).
Press `h` at any time to see the help menu.

### Find the Code Documentation

[Documentation is available here.](http://10.3.10.20/docs/)

### Install the Webapp locally

```bash
npm i
npm run dev
```

### Network Connections

The vci-webapp connects via network (vci-websocket) to the rest of the capture stage architecture:

 - Control Server. (vci-control repo).  This server controls the trigger box, timing image capture across all cameras.
 - Vci Automation. (vci-automation repo) Scipts to orchestrate camera calibration and image capture tasks across all capture servers.
 - Capture Servers (multiple vci-capture repo instances). Servers interfacing with and controlling the cameras.

When the webapp is running, the IP addresses of each can be configured in the `Settings` page.

For **fully local development** a test setup of [vci-automation](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-automation) and [vci-capture](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-capture) may be set up.
Clone and setup both repos locally.
The vci-capture server can be started with simulated cameras as per its ReadMe.

Vci-automation uses its own connection settings, pointing it to the capture servers, independet of vci-webapp. Because of this you need to update its `config/system_layout.json` (Simply rename the existing system_layout_sim.json to system_layout.json). Next, you can start its api-server as per its ReadMe.

In the webapp `Settings` page: set the ip-adresse of Vci Automation and the Capture Servers to '127.0.0.1' (localhost)


### Add functionality from a server

1. Find the [network module](src/network/) or its [docs](http://10.3.10.20/docs/modules/network.html)
2. Depending on which server implements the functionality you want to add,
   go to [ControlServer.tsx](src/network/control-server/ControlServer.tsx) or [CaptureServer.tsx](src/network/capture-server/CaptureServer.ts). Add methods for sending a message to the server there. Use the onResponse method to handle the response from the server. If the functionality is more complex or does not follow this request-response pattern, add your functionality in a derived class of InterceptorConnection, as done in [CaptureServerConnection.tsx](src/network/capture-server/CaptureServerConnection.tsx).
3. Add Hooks and UI components.

### Update Code Documentation

Run `npm run docs` to generate typedoc documentation locally.

Docs are written to `/public/docs/` because they are served together with the webapp.
If you want to update the hosted documentation, push your code changes to the remote repo and deploy your new version, see the [Deploy](#deploy) section below.

### Update the ximea manual

Run `npm run fetch-manual` to download and crawl the ximea manual for integrating it into the parameters page

### Deploy

The webapp is deployed [here](http://10.3.10.20/).
To deploy the newest version, open the `vci-control` repo on the control server (10.3.10.20, folder `/srv/vci/vci-control/`) and run the ansible playbook to deploy the webapp:

```bash
ansible-playbook -i ansible/inventory/inventory.yml ansible/roles/deploy_vci_webapp/run.yml 
```

You will need to enter a username and password for the control server with admin rights.
You will be prompted to provide your Gitlab username and password.
