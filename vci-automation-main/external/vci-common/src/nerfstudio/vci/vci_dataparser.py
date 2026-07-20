# Copyright 2022 the Regents of the University of California, Nerfstudio Team and contributors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Data parser for vci dataset"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Type, Optional, Literal

import threading
import imageio
from PIL import Image
import numpy as np
import torch
import os
import json

from nerfstudio.cameras.cameras import Cameras, CameraType
from nerfstudio.data.dataparsers.base_dataparser import DataParser, DataParserConfig, DataparserOutputs
from nerfstudio.data.scene_box import SceneBox
from nerfstudio.utils.colors import get_color
from nerfstudio.utils.io import load_from_json


@dataclass
class VCIDataParserConfig(DataParserConfig):
    """VCI dataset parser config"""

    _target: Type = field(default_factory=lambda: VCI)
    """target class to instantiate"""
    data: Path = Path("data/vci/sample_0013")
    """Directory specifying location of data."""
    frame: int = 0
    """Frame index to reconstruct."""
    scale_factor: float = 1.0
    """How much to scale the camera origins by."""
    bbox_size: Literal["include_cams", "exclude_cams", "stage_center", "tight"] = "stage_center"
    """Size of the bounding box of the scene"""
    precompute_rgba: bool = True
    """ Use images and masks to build RGBA images (png). """
    precompute_background: bool = False
    """ Use masks to set background color (alpha_color). """
    alpha_color: str = "white"
    """ Background color when baked to images. """
    fix_coordinate_system: bool = False
    """Fix for old camera centered coordinate system"""

@dataclass
class VCI(DataParser):
    """VCI Dataset
    Some of this code comes from https://github.com/yenchenlin/nerf-pytorch/blob/master/load_blender.py#L37.
    """

    config: VCIDataParserConfig

    def __init__(self, config: VCIDataParserConfig):
        super().__init__(config=config)
        self.config = config
        self.data: Path = Path(config.data)
        self.frame = config.frame
        self.scale_factor: float = config.scale_factor
        self.alpha_color = config.alpha_color
        if self.alpha_color is not None:
            self.alpha_color_tensor = get_color(self.alpha_color)
        else:
            self.alpha_color_tensor = None
        self.bbox_size = config.bbox_size
        self.precompute_rgba = config.precompute_rgba
        self.precompute_background = config.precompute_background

    @staticmethod
    def _flexy_load_image(path: Path) -> np.ndarray:
        """Load image as H,W,C float np array in [0,1]

        Args:
            path (Path): image path

        Returns:
            np.ndarray: image array
        """
        path = Path(path)
        if not path.is_file():
            matches = list(path.parent.glob(f"{path.stem}.*"))
            if len(matches) == 0:
                raise RuntimeError(f"No such file {path}")
            path = matches[0]
        with Image.open(path) as img:
            np_img = np.array(img)
        np_img = np_img.astype(np.float32) / 255
        return np_img

    @staticmethod
    def _save_image(path: Path, image: np.ndarray) -> None:
        """Save H,W,C float np array in [0,1] as image

        Args:
            path (Path): image path
            image (np.ndarray): image array
        """
        image = (image * 255).clip(0, 255).astype(np.uint8)
        Image.fromarray(image).save(path)

    def _fix_coordinate_system(self, extrinsics):
        inv_extrinsics = np.linalg.inv(extrinsics)
        rotation = inv_extrinsics[:3, :3]
        position = inv_extrinsics[:3, -1]
        mat = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)
        extrinsics[:3, :3] = mat @ rotation.T @ mat
        extrinsics[:3, -1] = -mat @ rotation.T @ position
        if self.config.fix_coordinate_system:
            t_calib = np.array(
                [
                    [-4.37114e-08, -0.987688, 0.156434, 0],
                    [1, -4.31732e-08, 6.83797e-09, 0],
                    [0, 0.156434, 0.987688, 0],
                    [0, 1.53, 2.4, 1],
                ],
            ).T
            extrinsics = extrinsics @ np.linalg.inv(t_calib)
        extrinsics = np.linalg.inv(extrinsics)
        t_gl = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32)
        extrinsics[:3,:] = t_gl @ extrinsics[:3,:]
        if not self.config.fix_coordinate_system:
            up_is_down = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)
            extrinsics[:3,:] = up_is_down @ extrinsics[:3,:]
        return extrinsics

    def rot_matrices(self,degr):
        rad = (degr/360) * 2*np.pi
        Rx = np.array([[1,0,0],
                       [0,np.cos(rad),-np.sin(rad)],
                       [0,np.sin(rad),np.cos(rad)]])
        Ry = np.array([[np.cos(rad),0,np.sin(rad)],
                       [0,1,0],
                       [-np.sin(rad),0,np.cos(rad)]])
        Rz = np.array([[np.cos(rad),-np.sin(rad),0],
                       [np.sin(rad),np.cos(rad),0],
                       [0,0,1]])

        return Rx, Ry, Rz

    def rot_world_x(self, degr):
        rad = (degr/360) * 2*np.pi
        return np.array([
            [ np.cos(rad), np.sin(rad), 0, 0],
            [-np.sin(rad), np.cos(rad), 0, 0],
            [           0,           0, 1, 0],
            [           0,           0, 0, 1]
        ])

    def rot_world_y(self, degr):
        rad = (degr/360) * 2*np.pi
        return np.array([
            [ np.cos(rad), 0, np.sin(rad), 0],
            [   0, 1,   0, 0],
            [-np.sin(rad), 0, np.cos(rad), 0],
            [   0, 0,   0, 1]
        ])
        

    # check that file exists, return extension or None if does not exist
    def check_file(self, dir, prefix):
        for s in os.listdir(dir):
            n = os.path.splitext(s)
            if n[0] == prefix and os.path.isfile(os.path.join(dir, s)):
                return n[1]
        return None

    def _generate_dataparser_outputs(self, split="train"):
        if (self.data / "calibration.json").exists():
            with open(os.path.join(self.data, 'calibration.json'), 'r') as fp:
                meta = json.load(fp)
        elif (self.data / "calibration_dome.json").exists():
            with open(os.path.join(self.data, 'calibration_dome.json'), 'r') as fp:
                meta = json.load(fp)
        else:
            raise RuntimeError(f"Calibration file not found in {self.data}, exiting")

        image_filenames = []
        poses = []
        intrinsics = []

        num_cams = len(meta['cameras'])
        #i_test = np.array([num_cams-1])
        i_test = [0,1] # np.array([0])
        #i_train = np.delete(np.arange(num_cams),i_test)
        i_train = np.arange(num_cams)
        if split == "train":
            cams = i_train
        elif split == "test":
            cams = i_test
        elif split == "val":
            cams = i_test
        else:
            raise ValueError(f"unknown split: {split} ")

        frame_dir = self.data / f"frame_{self.frame:05d}"
        rgb_dir = frame_dir / "rgb"
        mask_dir = frame_dir / "mask"
        background_dir = self.data / "background"
        rgba_dir = frame_dir / "rgba"
        masked_dir = frame_dir / "rgb_masked"
        if self.precompute_rgba:
            os.makedirs(rgba_dir, exist_ok=True)
        if self.precompute_background:
            os.makedirs(masked_dir, exist_ok=True)
        if (self.precompute_background or self.precompute_rgba) and not mask_dir.is_dir():
            raise ValueError(f"Missing mask dir {mask_dir}.")

        threads = []
        for i, frame in enumerate(meta['cameras']):
            if frame['camera_id'][0] == "M":
                print(f"Skipping mono camera {i+1}/{len(meta['cameras'])} [{frame['camera_id']}]")
                continue
            if i not in cams:
                continue # only read split
            print(f"Loading camera {i+1}/{len(meta['cameras'])} [{frame['camera_id']}]")

            ext = self.check_file(rgb_dir,frame['camera_id'])
            if ext is None:
                print("Missing image")
                continue # image does not exist
            if self.precompute_background or self.precompute_rgba:
                mask_name = f"mask_{frame['camera_id']}"
                m_ext = self.check_file(mask_dir, mask_name)
                if m_ext is None:
                    raise RuntimeError(f"Missing mask {mask_name}")

            # load data
            fname = os.path.join(rgb_dir, frame['camera_id'] + ext)
            with Image.open(fname) as img:
                W, H = img.size
            # W = frame['intrinsics']['resolution'][0]
            # H = frame['intrinsics']['resolution'][1]
            intr = np.reshape(np.array(frame['intrinsics']['camera_matrix']),(3,3))
            pose = np.reshape(np.array(frame['extrinsics']['view_matrix']),(4,4))
            pose = self._fix_coordinate_system(pose)
            if self.precompute_background or self.precompute_rgba:
                mname = os.path.join(mask_dir, f"mask_{frame['camera_id']}" + m_ext)

            # adjust intrinsics
            saved_res_w = frame['intrinsics']['resolution'][0]
            ratio_w = saved_res_w/W
            intr = intr/ratio_w
            intr[2,2] = 1.
            
            if self.precompute_rgba:
                fname_rgb = fname
                fname: Path = (rgba_dir / (frame['camera_id'] + ext)).with_suffix(".png")
                fname_bg = os.path.join(background_dir, frame['camera_id'] + ext)
                if not os.path.exists(fname):
                    print(f"Baking RGBA image {fname}")
                    def bake_rgba(fname_rgb, mname, fname_bg, fname):
                        im = VCI._flexy_load_image(fname_rgb)
                        mask = VCI._flexy_load_image(mname)
                        bg = VCI._flexy_load_image(fname_bg)
                        if mask.ndim == 2:
                            mask = mask[:,:,None]
                        elif mask.ndim == 3:
                            mask = mask[:,:,:1]
                        else:
                            raise ValueError("What?")
                        mask3 = np.repeat(mask, 3, 2)
                        valid_mask3 = mask3 >= 1.e-4
                        fg = np.zeros_like(im)
                        fg[valid_mask3] = (im[valid_mask3] - (1 - mask3[valid_mask3]) * bg[valid_mask3])# / mask3[valid_mask3]
                        fg = fg.clip(0, 1)
                        masked_image = np.concatenate([fg, mask], 2)
                        self._save_image(fname, masked_image)
                    t = threading.Thread(
                        target=bake_rgba,
                        args=(fname_rgb, mname, fname_bg, fname)
                    )
                    t.start()
                    threads.append(t)

            if self.precompute_background:
                fname_rgb = fname
                fname = os.path.join(masked_dir, frame['camera_id'] + ext)
                if not os.path.exists(fname):
                    print("Baking masked background image")
                    im = imageio.imread(fname_rgb)
                    im = im.astype(np.float32) / 255
                    mask = imageio.imread(mname)[:,:,None].astype(np.float32) / 255
                    masked_image = mask * im + (1 - mask) * self.alpha_color_tensor.numpy()
                    masked_image = (255*masked_image).astype(np.uint8)
                    imageio.imwrite(fname, masked_image)

            image_filenames.append(fname)
            poses.append(pose)
            intrinsics.append(intr)

        for t in threads:
            t.join()
        threads = []
    
        poses = np.array(poses).astype(np.float32)
        intrinsics = torch.from_numpy(np.array(intrinsics).astype(np.float32))
        fx=intrinsics[:,0,0]
        fy=intrinsics[:,1,1]
        cx=intrinsics[:,0,2]
        cy=intrinsics[:,1,2]

        # fix camera positions
        Rx, Ry, Rz = self.rot_matrices(180)
        # poses[:,:3,3] = -np.einsum('BNi,Bi ->BN',np.transpose(poses[:,:3,:3],(0,2,1)), poses[:,:3,3])#.ravel()
        # poses[:,:3,:3] = np.transpose(poses[:,:3,:3],(0,2,1))
        # poses[:,:3,:3] = np.matmul(poses[:,:3,:3],Ry)
        # poses[:,:3,:3] = np.matmul(poses[:,:3,:3],Rz)
    
        # for i in range(poses.shape[0]):
        #     poses[i,:,:] = self.rot_world_y(90) @ poses[i,:,:]
        #     poses[i,:,:] = self.rot_world_x(20) @ poses[i,:,:]
        # poses = poses[:,:3,:]
        camera_to_world = torch.from_numpy(poses[:, :3])  # camera to world transform

        # in x,y,z order
        camera_to_world[..., 3] *= self.scale_factor
        # if self.bbox_size == "exclude_cams":
        #     scene_box = SceneBox(aabb=self.scale_factor*torch.tensor([[-2.5, 0, -2.5], [2.5, 3.0, 2.5]], dtype=torch.float32)) # bounds only center of stage
        if self.bbox_size == "include_cams":
            scene_box = SceneBox(aabb=self.scale_factor*torch.tensor([[-4.0, -4.0, -0.5], [4.0, 4.0, 3.0]], dtype=torch.float32))
        elif self.bbox_size == "stage_center":
            scene_box = SceneBox(aabb=self.scale_factor*torch.tensor([[-1.25, -1.25, -0.2], [1.25, 1.25, 2.8]], dtype=torch.float32))
        elif self.bbox_size == "tight":
            scene_box = SceneBox(aabb=self.scale_factor*torch.tensor([[-0.5, -0.5, -0.2], [0.5, 0.5, 1.8]], dtype=torch.float32))
        else:
            raise ValueError()
            scene_box = SceneBox(aabb=self.scale_factor*torch.tensor([[-4.6, -4.7, -2.5], [4.7, 4.9, 7.4]], dtype=torch.float32)) # bound including dome

        cameras = Cameras(
            camera_to_worlds=camera_to_world,
            width = W,
            height = H,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            camera_type=CameraType.PERSPECTIVE,
        )

        dataparser_outputs = DataparserOutputs(
            image_filenames=image_filenames,
            cameras=cameras,
            scene_box=scene_box,
            # dataparser_scale=self.scale_factor,
            #metadata = {"mask_color": [1.0,1.0,1.0]},
        )

        return dataparser_outputs
