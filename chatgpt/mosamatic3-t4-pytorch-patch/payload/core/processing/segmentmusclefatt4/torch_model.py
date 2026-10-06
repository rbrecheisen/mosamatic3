"""TorchScript-only T4 model loading and inference. No Django dependencies."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import torch


MODEL_EXTENSIONS = (".pt", ".pth", ".ts", ".zip")


def load_torchscript_model(path: Path) -> torch.jit.ScriptModule:
    """Load a self-contained TorchScript module (also supports an outer ZIP)."""
    try:
        model = torch.jit.load(str(path), map_location="cpu")
    except Exception as original_exc:
        if path.suffix.lower() != ".zip" or not zipfile.is_zipfile(path):
            raise RuntimeError(
                f"Cannot load {path.name} as TorchScript. A PyTorch state_dict "
                "(.pth/.pt checkpoint) requires the original model architecture; "
                "export a self-contained TorchScript model with torch.jit.save(). "
                f"Original error: {original_exc}"
            ) from original_exc

        with zipfile.ZipFile(path) as archive:
            candidates = [
                info for info in archive.infolist()
                if not info.is_dir()
                and Path(info.filename).suffix.lower() in (".pt", ".pth", ".ts")
                and not info.filename.startswith("__MACOSX/")
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    f"{path.name} is not a TorchScript archive and must contain "
                    "exactly one TorchScript .pt/.pth/.ts file (found "
                    f"{len(candidates)})."
                ) from original_exc
            try:
                with archive.open(candidates[0]) as member:
                    model = torch.jit.load(io.BytesIO(member.read()), map_location="cpu")
            except Exception as exc:
                raise RuntimeError(
                    f"File {candidates[0].filename} in {path.name} is not a "
                    "self-contained TorchScript model. If it is a state_dict, "
                    "the network definition and checkpoint format are required. "
                    f"Original error: {exc}"
                ) from exc

    model.eval()
    return model


def normalize_ct(image: np.ndarray, config: dict) -> np.ndarray:
    """Normalization must match T4 training; legacy matches the existing L3 implementation."""
    method = config.get("normalization", "l3_legacy")
    image = np.asarray(image, dtype=np.float32)
    if image.ndim != 2:
        raise ValueError(f"Expected a single axial 2D DICOM slice, got shape {image.shape}")
    if method == "none":
        return image

    minimum, maximum = config.get("min_bound"), config.get("max_bound")
    if minimum is None or maximum is None or float(maximum) <= float(minimum):
        raise ValueError("T4 params require min_bound < max_bound for CT normalization")
    minimum, maximum = float(minimum), float(maximum)
    if method == "clip_linear":
        return np.clip((image - minimum) / (maximum - minimum), 0, 1).astype(np.float32)
    if method == "l3_legacy":
        # Preserve exact existing L3 normalize_between behavior (including upper clipping to zero).
        from core.common.utils import normalize_between
        return normalize_between(image, minimum, maximum).astype(np.float32)
    raise ValueError(f"Unknown T4 normalization '{method}' (none/clip_linear/l3_legacy)")


def _extract_tensor(result):
    if isinstance(result, dict):
        for key in ("out", "logits", "prediction"):
            if key in result:
                return _extract_tensor(result[key])
        raise ValueError(f"T4 model returned an unsupported output dictionary: {list(result)}")
    if isinstance(result, (tuple, list)):
        if not result:
            raise ValueError("T4 model returned an empty tuple/list")
        return _extract_tensor(result[0])
    if not isinstance(result, torch.Tensor):
        raise ValueError(f"T4 model must output a Tensor, received {type(result).__name__}")
    return result.detach().cpu()


def predict_t4(image: np.ndarray, model, config: dict, *, probabilities: bool,
               enforce_class_count: bool = True) -> np.ndarray:
    """Return class indices (H,W) or probability maps (H,W,C)."""
    input_layout = config.get("input_layout", "NCHW").upper()
    output_layout = config.get("output_layout", "NCHW").upper()
    if input_layout not in ("NCHW", "NHWC") or output_layout not in ("NCHW", "NHWC"):
        raise ValueError("T4 input_layout and output_layout must be NCHW or NHWC")

    tensor = torch.from_numpy(np.ascontiguousarray(image, dtype=np.float32))
    tensor = tensor[None, None, :, :] if input_layout == "NCHW" else tensor[None, :, :, None]
    with torch.inference_mode():
        prediction = _extract_tensor(model(tensor))

    h, w = image.shape
    if prediction.ndim == 4:
        if prediction.shape[0] != 1:
            raise ValueError(f"T4 prediction batch size must be 1: {tuple(prediction.shape)}")
        prediction = prediction[0]
        if output_layout == "NCHW":
            prediction = prediction.permute(1, 2, 0)
        if tuple(prediction.shape[:2]) != (h, w):
            raise ValueError(
                f"T4 prediction spatial shape {tuple(prediction.shape[:2])} "
                f"does not match DICOM {(h, w)} (output_layout={output_layout})"
            )
        class_count = prediction.shape[-1]
        if class_count < 2:
            raise ValueError("T4 class-channel output must have at least two classes")
        if enforce_class_count and class_count != len(config["class_labels"]):
            raise ValueError(
                f"T4 model outputs {class_count} class channels, but class_labels "
                f"defines {len(config['class_labels'])} classes"
            )
        if probabilities:
            activation = config.get("output_activation", "logits").lower()
            if activation == "logits":
                prediction = torch.softmax(prediction.float(), dim=-1)
            elif activation != "probabilities":
                raise ValueError("T4 output_activation must be logits or probabilities")
            return prediction.numpy().astype(np.float32)
        return prediction.argmax(dim=-1).numpy().astype(np.int64)

    if prediction.ndim == 3 and prediction.shape[0] == 1:
        prediction = prediction[0]
    if prediction.ndim == 2 and tuple(prediction.shape) == (h, w):
        if probabilities:
            raise ValueError("T4 model already outputs discrete labels; probabilities are unavailable")
        if prediction.is_floating_point() and not torch.all(prediction == prediction.round()):
            raise ValueError("T4 model output is 2D floating values, not discrete class labels")
        return prediction.numpy().astype(np.int64)
    raise ValueError(f"Unsupported T4 prediction shape {tuple(prediction.shape)}")


def map_labels(class_indices: np.ndarray, config: dict) -> np.ndarray:
    """Map training class IDs to the application's 0/1/5/7 tissue convention."""
    labels = config.get("class_labels", [0, 1, 5, 7])
    if not isinstance(labels, list) or not labels or any(type(x) is not int for x in labels):
        raise ValueError("T4 params class_labels must be an integer list (e.g. [0,1,5,7])")
    if any(x not in (0, 1, 5, 7) for x in labels):
        raise ValueError("T4 class_labels may contain only 0 (background), 1 (muscle), 5 (VAT), 7 (SAT)")
    if len(set(labels)) != len(labels):
        raise ValueError("T4 class_labels must contain unique tissue labels")
    if class_indices.size and (
        np.min(class_indices) < 0 or np.max(class_indices) >= len(labels)
    ):
        raise ValueError(
            f"T4 output contains class IDs outside 0..{len(labels)-1}; "
            "check class_labels and model output format"
        )
    return np.asarray(labels, dtype=np.uint8)[class_indices]
