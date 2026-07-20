from pathlib import Path

import torch

import sparrow.gibbs_wrapper as gibbs

from .model.model import MattingRefine


class MattingInference(torch.nn.Module):
    def __init__(
        self,
        model_checkpoint: Path = Path(__file__).parent / "weights" / "pytorch_mobilenetv2.pth",
        model_backbone: str = "mobilenetv2",
        model_backbone_scale: float = 0.25,
        model_refine_mode: str = "sampling",
        model_refine_sample_pixels: int = 80000,
        model_refine_threshold: float = 0.7,
        model_refine_kernel_size: int = 3,
        device: str = "cuda",
    ) -> None:
        """
        Initializes the MattingInference class.

        Args:
            model_checkpoint (str): Path to the model checkpoint.
            model_backbone (str): Backbone model to use, default is 'mobilenetv2'.
            model_backbone_scale (float): Scale of the backbone model, default is 0.25.
            model_refine_mode (str): Refinement mode, default is 'sampling'.
            model_refine_sample_pixels (int): Number of sample pixels for refinement, default is 80000.
            model_refine_threshold (float): Threshold for refinement, default is 0.7.
            model_refine_kernel_size (int): Kernel size for refinement, default is 3.
            device (str): Device to run the model on, default is 'cuda'.
        """
        super().__init__()

        self.device = device

        if model_checkpoint is None:
            model_checkpoint = Path(__file__).parent / "weights" / "pytorch_mobilenetv2.pth"

        self.model = MattingRefine(
            model_backbone,
            model_backbone_scale,
            model_refine_mode,
            model_refine_sample_pixels,
            model_refine_threshold,
            model_refine_kernel_size,
        )
        self.model = self.model.to(device).eval()
        cpt = torch.load(model_checkpoint, map_location=device, weights_only=True)
        self.model.load_state_dict(cpt, strict=False)

    def forward(self, src: torch.Tensor, bgr: torch.Tensor) -> tuple[torch.tensor, torch.tensor]:
        """
        Performs matting inference on the provided foreground and background image.

        Args:
            src (torch.Tensor): Foreground image tensor [Bx3xHxW]
            bgr (torch.Tensor): Background image tensor [Bx3xHxW]
            meta_in (dict): Input meta data

        Returns:
            torch.Tensor: The alpha matte of the foreground image [Bx1xHxW]
            torch.Tensor: The foreground image [Bx3xHxW]
        """
        with torch.no_grad():
            pha, fgr, _, _, err, ref = self.model(src, bgr)
        return pha, fgr

    def save_torchscript(self, file_path: str) -> None:
        net = torch.jit.script(self)
        net = torch.jit.optimize_for_inference(net)
        net.save(file_path)

    def infer(self, foreground: gibbs.GibbsImage, background: gibbs.GibbsImage) -> gibbs.GibbsImage:
        if foreground.image_type != background.image_type:
            msg = "Foreground and background image type must match."
            raise TypeError(msg)

        fg: torch.tensor = foreground.get_mattable_tensor(torch.float32)
        bg: torch.tensor = background.get_mattable_tensor(torch.float32)

        mask: torch.tensor = self.forward(fg, bg)[0][0]
        ret = gibbs.GibbsImage(mask, foreground.camera_id, foreground.image_type, foreground.pixel_layout)
        ret.data_category = gibbs.DataCategory.Matte
        return ret
