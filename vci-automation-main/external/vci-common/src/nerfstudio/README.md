# Nerfstudio VCI Dataloader

Utility class to load vci data directly into Nerfstudio.

## Setup

Setup a working nerfstudio environment first. I recommend following the official guide here:

[https://docs.nerf.studio/quickstart/installation.html](https://docs.nerf.studio/quickstart/installation.html)

Then, install the dataloader (where `.` should be this directory):

```sh
pip install -e .
```

## Usage

Some hints:

- I recommend `nerfacto-big` or `nerfacto-huge`
- `max-num-iterations` is `100000` per default but less also works.
  `10000` is fine if you use 4 GPUs
- `near-plane` and `far-plane` need to have the `scale_factor` already applied, i.e. the true planes are `* scale_factor`
- `data` should point to the directory containing the calibration file and the frame directories
- `fix_coordinate_system` adjusts the old calibration file centered around one camera

```sh
ns-train \
  nerfacto-big \
  --max-num-iterations 10000 \
  --logging.steps-per-log 100 \
  --steps-per-eval-image 1000 \
  --machine.num-devices 4 \
  --pipeline.model.near-plane 0.2 \
  --pipeline.model.far-plane 2.0 \
  --pipeline.model.background-color random \
  --experiment-name test \
  --pipeline.model.camera-optimizer.mode off \
  --pipeline.model.disable-scene-contraction False \
  --pipeline.model.use_appearance_embedding False \
  --pipeline.model.proposal_initial_sampler uniform \
  --pipeline.model.predict_normals False \
  --pipeline.datamanager.images-on-gpu True \
  --pipeline.datamanager.masks-on-gpu True \
  vci-data \
  --data path/to/data/dir \
  --frame 0 \
  --scale_factor 0.2 \
  --bbox_size tight \
  --fix_coordinate_system False
```