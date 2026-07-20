# vci-capture

**[MORE Documentation HERE!!!!](/documentation/)**

vci-capture is the base building block of the capture stage architecture. 
It runs on a computer interfacing with mutiple cameras, handling camera connection, image capture and data storage.
The central usecase of this repo is to run the server:

Run Server:
```sh
python src/sparrow/server.py
```

Run Server with automatic restart after crash
```sh
scripts/run.sh
```

The server opens the cameras, loads configs and then idles, listening to API requests (sent via vci-websocket connection).
The repos vci-automation, vci-webapp as well as RIFTCast connect to the vci-capture server to perform tasks like:
camera calibration, image capture (orchestrated across multiple vci-capture servers), live streams and 3D Reconstruction.

Since we usually run multiple vci-capture servers concurrently on different machines, this repo does not contain 
scripts for standanlone caputre and other tasks. 
Though you can find a few scripts in tests/playground, for development.
Instead you are encouraged to use vci-automation or webapp for common tasks.

## Supported Cameras

- Ximea (MX245MG-SY-X4G3-xx and MX245CG-SY-X4G3-xx)
- Basler (a2A4096-67cc)
- Orbbec
- simulated cameras

Alternatively you can run the server with simulated cameras:
```sh
python src/sparrow/server.py --sim
or
scripts/run_simulated.sh
```

## Setup

To enable the connection to the cameras, you need to install the cameras' SKD provided by their Manufactuer on your machine.

### Setup with Docker

For (local) development,
you can start a docker container using the provided compose file:

```sh
docker compose build # Only needed once or when Dockerfile changes
docker compose up -d # -d for detached mode
```

The docker is stopped with:
```sh
docker compose down
```


Should you run into problems while starting the docker container:
1. Make sure your docker is not installed with snap (permission problems may arise and paths are incorrect). If it is, uninstall docker via `sudo snap remove docker --purge` to avoid any problems with later installs. Follow the [official Install guide](https://docs.docker.com/engine/install/ubuntu/).
2. If you face `Docker Error - Unknown or Invalid Runtime Name: Nvidia` make sure to install the [nvidia container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Afterwards you can pass the following
```
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```
This should get you up and running to call the docker commands from above.

You can then attach to it using VS Code
(`Dev Containers: Attach to Running Container`).
You'll find the code in `/srv/vci-capture`.
To shut it down again, run `docker compose down`.

To install the recommended extensions, go to the Extensions view (Ctrl+Shit+x), search for `@recommended` and install workspace recommendations, or install when prompted.

The build type can be controlled via the environment variable `GIBBS_BUILD_TYPE`.
If it is not set, the default `RelWithDebInfo` will be used.

There is a C++ and a Python debug launch configuration in `.vscode/launch.json` that start `sparrow/server.py`.
The gdb variant will automatically set the build type to `Debug`.
For joint C++/Python debugging manual attaching gdb to a started program is needed, have fun with that.
There is also a (pythoncpp-debug)[https://marketplace.visualstudio.com/items?itemName=benjamin-simmonds.pythoncpp-debug]
extension that might or might not work for you.
Configuring python-gdb would also be nice, but is left as an exercise for the reader.


When using **git with docker** you cannot use git from inside the docker (attached to it). 
When you create files inside the docker, you can mess up folder/file permissions, resulting in 
an *error: unable to unlink/create <file>: Permission denied*.

Checking the current permissions:
`ls -l .`
The rights for push-able folders/files should be user *hector docker* (not *root root*)
You can set this for a folder or file with:
`sudo chown hector:docker <file or folder>`


### Setup without docker

#### CUDA toolkit
Install the CUDA toolkit that your gpu+system requires.
Check that nvcc is installed with ```nvcc --version```.
If you can't find nvcc but it's installed make sure to add it to the PATH environment variable.
Otherwise vci-capture won't find it either.

For Ubuntu you can add it to the bashrc file:
```sh
nano ~/.bashrc
```
Add to the end of file:
```sh
# Add Cuda paths for nvcc and libraries
export PATH=/usr/local/cuda-XX.X/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda-XX.X/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
```

#### vci-capture venv
Create a venv and activate it. 

Install dependencies:

```sh
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
pip submodule update --init
pip install -e external/vci-websocket/
```

## Test

Test SDK discovery and hardware discovery:
```sh
python scripts/check_cameras.py
```

Pytests for pipeline (simualted cameras only):
```sh
python -m pytest tests/pipeline -sx
```

Pytests for testing full API:
```sh
python -m pytest tests/integration -sx ## --hardware for real cameras
```

If pytest the flag `-s` prints console output (otherwise output is suppressed) and `-x` stops after the first test fails.

## Run server

Run Server:
```sh
python src/sparrow/server.py # --sim for simualted cameras
```

Run Server with automatic restart after crash
```sh
scripts/run.sh
```