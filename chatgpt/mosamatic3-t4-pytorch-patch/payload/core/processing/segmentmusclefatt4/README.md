# T4 PyTorch model interface

This task loads **self-contained TorchScript** models on CPU. PyTorch is already
specified in `pyproject.toml`; a **rebuild/restart of web + Celery workers** is
required to register the new task. Raw `torch.save(model.state_dict(), ...)`
checkpoints are **not executable models** and cannot be loaded without their
original Python architecture. `torch.load(weights_only=False)` is deliberately
not used.

Place the following files in the directory configured by
`BUILTIN_T4_MODEL_FILES_DIR` (normally `core/systemdatasets/modelfiles_t4/`), then
run `python manage.py ensure_systemdatasets` in the Django container:

- `model-1.0.pt`: TorchScript produced with `torch.jit.script` or
  `torch.jit.trace`, saved via `torch.jit.save`; alternatively `model-1.0.pth`,
  `model-1.0.ts` or `model-1.0.zip` containing **one** TorchScript file.
- `params-1.0.json`: required preprocessing and output format configuration.
- `contour_model-1.0.pt`: optional TorchScript model producing nonzero contour
  mask classes. Can also be `.pth`, `.ts`, or `.zip`.

Example `params-1.0.json` for a **four-class, NCHW, logits** TorchScript model
trained on the same legacy CT normalization as L3:

```json
{
  "min_bound": -200,
  "max_bound": 250,
  "normalization": "l3_legacy",
  "input_layout": "NCHW",
  "output_layout": "NCHW",
  "output_activation": "logits",
  "class_labels": [0, 1, 5, 7]
}
```

The bounds here are **examples**, not verified values for the T4 model.
You MUST replace them with the preprocessing values used in T4 training.
Supported normalization: `l3_legacy` (identical to existing L3 task),
`clip_linear` (clip to [0, 1]), and `none` (raw HU). Optional contour models
need `min_bound_contour` and `max_bound_contour` too.

`input_layout` and `output_layout` are `NCHW` (PyTorch default) or `NHWC`.
Output may be `[1,C,H,W]`, `[1,H,W,C]`, or a 2D integer class-index mask.
Tensor/dict(`out` or `logits`)/tuple outputs are supported. Channel output
should represent `[background, muscle, VAT, SAT]` if you use the example mapping.
Set `class_labels` to match the **actual** training class order, mapping each
class index to 0=background, 1=muscle, 5=VAT, 7=SAT. Incorrect mapping yields
incorrect body-composition scores. `output_activation` is `logits` (softmax
applied for probabilities) or `probabilities` (already normalized).

Hard segmentation output: `image.dcm.seg.npy`, matched to copied `image.dcm`.
Probability output: `image.dcm_prob.seg.npy` (not compatible with scoring).
The T4 pipeline sets probabilities false and uses the existing `Calculate Scores`
task. That task exports raw tissue areas, indices and attenuation; note that any
L3-based clinical cutoffs (such as sarcopenia criteria) are **not validated** at
T4 and should not be applied to T4 outputs without a separate validation.

A TorchScript export from the original training environment typically resembles:

```python
model.load_state_dict(torch.load("checkpoint.pth", map_location="cpu", weights_only=True))
model.eval()
example = torch.randn(1, 1, 512, 512)
traced = torch.jit.trace(model, example)
traced.save("model-1.0.pt")
```

This is only a schematic example: `model` must first be constructed from the
**correct network class**, the correct checkpoint keys must be used, and the
example shape/preprocessing must match training. Script rather than trace if
control flow depends on inputs.
