## Matting

Matting networks are stored as serialized [TorchScript](https://docs.pytorch.org/docs/stable/jit.html) files.
The biggest advantage is that they can be loaded and called from C++ without any Python GIL surprises.
To save an existing model model as half precision, use the following code:

```python
model : torch.nn.Module = ...
model.to(dtype=torch.float16)
script_model = torch.jit.script(model)
script_model = torch.jit.optimize_for_inference(script_model)
script_model.save("vci-capture/weights/matting/<model_name>.<color_space>.<dtype>.pt")
```

The file name uses the following convention:

- `<model_name>` should be a descriptive name of the model
- `<color_space>` the intended image format (`rgb` or `ir`)
- `<dtype>` the models dtype (`float16` or `float32`)

The forward method of the model must use the following signature:

```python
    def forward(self, source: torch.Tensor, background: torch.Tensor) -> tuple[torch.tensor, torch.tensor]:
        # ...
        return mask, foreground
```

The tensors must have the following shapes, where `C` is 3 for RGB models and 1 for IR:

- `source`: B x C x H x W
- `background`: B x C x H x W
- `mask`: B x 1 x H x W
- `foreground`: B x C x H x W

If the method does not support foreground correction one can fall back to returning `source` as `foreground`.