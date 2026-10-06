# Segment Muscle/Fat T4 PyTorch

This task intentionally reproduces the T4 inference mechanism from Mosamatic2.

## Required model dataset files

For model version `1.0` the built-in T4 model dataset must contain exactly:

- `model-1.0.pt` — four-class body-composition UNet `state_dict`
- `contour_model-1.0.pt` — two-class contour UNet `state_dict`
- `params-1.0.json` — original Mosamatic2 parameter JSON

The `.pt` files are **not TorchScript**. The task reconstructs the UNet from the bundled
`models.py`, then calls `load_state_dict()` exactly as Mosamatic2 did.

## Parameters used during inference

The original parameter file can be used unchanged. T4 inference requires:

- `dropout_rate` to reconstruct the UNet
- `lower_bound` and `upper_bound` for image normalization

Other training fields may remain in the JSON and are ignored during inference.

## Inference sequence

1. Read the DICOM and convert stored pixels to HU with RescaleSlope/RescaleIntercept.
2. Apply the legacy Mosamatic `normalize_between(lower_bound, upper_bound)` function.
3. Run the 2-class contour UNet and multiply the normalized image by its predicted mask.
4. Run the 4-class body-composition UNet.
5. Take `argmax` over output classes.
6. Convert model classes `0,1,2,3` to Mosamatic labels `0,1,5,7`
   (background, muscle, VAT, SAT).

The bundled `models.py` already applies softmax in `UNet.forward()`.
