import time
import os
import click
import textwrap
import math
import pendulum
import numpy as np
import struct
import binascii
import warnings
from PIL import Image

warnings.filterwarnings("ignore", message="Invalid value for VR UI:", category=UserWarning)

MUSCLE, VAT, SAT = 1, 5, 7


def is_gpu_available(based_on='torch'):
    if based_on == 'torch':
        import torch
        return torch.cuda.is_available()
    elif based_on == 'tensorflow':
        import tensorflow as tf
        return len(tf.config.list_physical_devices('GPU')) > 0
    else:
        print(f'is_gpu_available() Unknown platform: {based_on}')
        return False


def create_name_with_timestamp(prefix: str='') -> str:
    tz = pendulum.local_timezone()
    timestamp = pendulum.now(tz).strftime('%Y%m%d%H%M%S%f')[:17]
    if prefix != '' and not prefix.endswith('-'):
        prefix = prefix + '-'
    name = f'{prefix}{timestamp}'
    return name


def show_doc_command(cli_group: click.Group) -> click.Command:
    @click.command(name="showdoc")
    @click.argument("command_name", required=False)
    def show_doc(command_name):
        commands = cli_group.commands
        if command_name:
            cmd = commands.get(command_name)
            if cmd and hasattr(cmd, 'callback') and cmd.callback.__doc__:
                print()
                print(textwrap.dedent(cmd.callback.__doc__).strip())
            else:
                click.echo(f'No docstring found for command: {command_name}')
        else:
            click.echo('Available commands with docstrings:')
            for name, cmd in commands.items():
                if hasattr(cmd, 'callback') and cmd.callback.__doc__:
                    click.echo(f"  {name}")
            click.echo('\nUse: `mosamatic show-doc <command>` to view a commands docstring')
    return show_doc


def current_time_in_milliseconds():
    return int(round(time.time() * 1000))


def current_time_in_seconds() -> int:
    return int(round(current_time_in_milliseconds() / 1000.0))


def elapsed_time_in_milliseconds(start_time_in_milliseconds):
    return current_time_in_milliseconds() - start_time_in_milliseconds


def elapsed_time_in_seconds(start_time_in_seconds):
    return current_time_in_seconds() - start_time_in_seconds


def duration(seconds):
    h = int(math.floor(seconds/3600.0))
    remainder = seconds - h * 3600
    m = int(math.floor(remainder/60.0))
    remainder = remainder - m * 60
    s = int(math.floor(remainder))
    return '{} hours, {} minutes, {} seconds'.format(h, m, s)


def is_numpy_array(value):
    return isinstance(value, np.array)


def is_numpy(f):
    try:
        np.load(f)
        return True
    except:
        return False


def load_numpy_array(f):
    if is_numpy(f):
        return np.load(f)
    return None


def get_pixels_from_tag_file(tag_file_path):
    f = open(tag_file_path, 'rb')
    f.seek(0)
    byte = f.read(1)
    # Make sure to check the byte-value in Python 3!!
    while byte != b'':
        byte_hex = binascii.hexlify(byte)
        if byte_hex == b'0c':
            break
        byte = f.read(1)
    values = []
    f.read(1)
    while byte != b'':
        v = struct.unpack('b', byte)
        values.append(v)
        byte = f.read(1)
    values = np.asarray(values)
    values = values.astype(np.uint16)
    return values


def convert_labels_to_157(label_image: np.array) -> np.array:
    label_image157 = np.copy(label_image)
    label_image157[label_image157 == 1] = 1
    label_image157[label_image157 == 2] = 5
    label_image157[label_image157 == 3] = 7
    return label_image157


def normalize_between(img: np.array, min_bound: int, max_bound: int) -> np.array:
    img = (img - min_bound) / (max_bound - min_bound)
    # img[img > 1] = 1
    img[img < 0] = 0
    img[img > 1] = 0
    c = (img - np.min(img))
    d = (np.max(img) - np.min(img))
    img = np.divide(c, d, np.zeros_like(c), where=d != 0)
    return img


def apply_window_center_and_width(image: np.array, center: int, width: int) -> np.array:
    image_min = center - width // 2
    image_max = center + width // 2
    windowed_image = np.clip(image, image_min, image_max)
    windowed_image = ((windowed_image - image_min) / (image_max - image_min)) * 255.0
    return windowed_image.astype(np.uint8)


def calculate_area(labels: np.array, label, pixel_spacing) -> float:
    mask = np.copy(labels)
    mask[mask != label] = 0
    mask[mask == label] = 1
    area = np.sum(mask) * (pixel_spacing[0] * pixel_spacing[1]) / 100.0
    return area


def calculate_index(area: float, height: float) -> float:
    return area / (height * height)


def calculate_bmi(weight: float, height: float) -> float:
    return weight / (height * height)


def calculate_sarcopenia(muscle_idx: float, bmi: float, sex: str) -> str:
    if not sex in ['male', 'female']:
        return 'unknown'
    if bmi >= 25 and muscle_idx < 53:
        return 'yes'
    if bmi < 25 and ((sex == 'male' and muscle_idx < 43) or (sex == 'female' and muscle_idx < 41)):
        return 'yes'
    return 'no'

def calculate_sarcopenic_obesity(muscle_idx: float, bmi: float, sex: str) -> str:
    if sex not in ['male', 'female']:
        return 'unknown'
    if bmi >= 25 and ((muscle_idx < 38.5 and sex == 'male') or (muscle_idx < 52.4 and sex == 'female')):
        return 'yes'
    return 'no'

def calculate_myosteatosis(smra: float, bmi: float) -> str:
    if (smra < 33 and bmi >= 25) or (smra < 41 and bmi < 25):
        return 'yes'
    return 'no'

def calculate_visceral_obesity(vat_area: float) -> str:
    if vat_area > 100:
        return 'yes'
    return 'no'

def calculate_mean_radiation_attenuation(image: np.array, labels: np.array, label: int) -> float:
    mask = np.copy(labels)
    mask[mask != label] = 0
    mask[mask == label] = 1
    subtracted = image * mask
    mask_sum = np.sum(mask)
    if mask_sum > 0.0:
        mean_radiation_attenuation = np.sum(subtracted) / np.sum(mask)
    else:
        mean_radiation_attenuation = 0.0
    return mean_radiation_attenuation


def calculate_lama_percentage(image: np.ndarray, labels: np.ndarray, label: int, threshold: float = 30.0) -> float:
    roi = (labels == label)
    n_roi = int(np.count_nonzero(roi))
    if n_roi == 0:
        return 0.0
    lama = roi & (image < threshold)
    lama_pct = (np.count_nonzero(lama) / n_roi) * 100.0
    return int(lama_pct)


def calculate_dice_score(ground_truth: np.array, prediction: np.array, label: int) -> float:
    numerator = prediction[ground_truth == label]
    numerator[numerator != label] = 0
    n = ground_truth[prediction == label]
    n[n != label] = 0
    if np.sum(numerator) != np.sum(n):
        raise RuntimeError('Mismatch in Dice score calculation!')
    denominator = (np.sum(prediction[prediction == label]) + np.sum(ground_truth[ground_truth == label]))
    dice_score = np.sum(numerator) * 2.0 / denominator
    return dice_score


class ColorMap:
    def __init__(self, name: str) -> None:
        self._name = name
        self._values = []

    def name(self) -> str:
        return self._name
    
    def values(self):
        return self._values
    

class GrayScaleColorMap(ColorMap):
    def __init__(self) -> None:
        super(GrayScaleColorMap, self).__init__(name='GrayScaleColorMap')
        # Implement your own gray scale map or let NumPy do this more efficiently?
        pass    

class AlbertaColorMap(ColorMap):
    def __init__(self) -> None:
        super(AlbertaColorMap, self).__init__(name='AlbertaColorMap')
        for i in range(256):
            if i == 1:  # muscle
                self.values().append([255, 0, 0])
            elif i == 2:  # inter-muscular adipose tissue
                self.values().append([0, 255, 0])
            elif i == 5:  # visceral adipose tissue
                self.values().append([255, 255, 0])
            elif i == 7:  # subcutaneous adipose tissue
                self.values().append([0, 255, 255])
            elif i == 12:  # unknown
                self.values().append([0, 0, 255])
            else:
                self.values().append([0, 0, 0])


def apply_color_map(pixels: np.array, color_map: ColorMap) -> np.array:
    pixels_new = np.zeros((*pixels.shape, 3), dtype=np.uint8)
    np.take(color_map.values(), pixels, axis=0, out=pixels_new)
    return pixels_new


def convert_numpy_array_to_png_image(
        numpy_array_file_path_or_object: str, output_dir_path: str, color_map: ColorMap=None, png_file_name: str=None, fig_width: int=10, fig_height: int=10) -> str:
    if isinstance(numpy_array_file_path_or_object, str):
        numpy_array = np.load(numpy_array_file_path_or_object)
    else:
        numpy_array = numpy_array_file_path_or_object
        if not png_file_name:
            raise RuntimeError('PNG file name required for NumPy array object')
    if color_map:
        numpy_array = apply_color_map(pixels=numpy_array, color_map=color_map)
    image = Image.fromarray(numpy_array)
    if not png_file_name:
        numpy_array_file_name = os.path.split(numpy_array_file_path_or_object)[1]
        png_file_name = numpy_array_file_name + '.png'      
    elif not png_file_name.endswith('.png'):
        png_file_name += '.png'
    png_file_path = os.path.join(output_dir_path, png_file_name)
    image.save(png_file_path)
    return png_file_path


def convert_muscle_mask_to_myosteatosis_map(hu: np.array, mask: np.array, output_dir: str, png_file_name: str, hu_low: int = 30, hu_high: int = 200, alpha: float = 1.0) -> str:
    muscle_mask = (mask == 1)
    red = muscle_mask & (hu >= hu_low) & (hu <= hu_high)
    yellow = muscle_mask & (hu < hu_low)
    overlay = np.zeros((*hu.shape, 4), dtype=np.float32)
    overlay[..., 3] = 1.0
    overlay[red] = (1.0, 0.0, 0.0, alpha)
    overlay[yellow] = (1.0, 1.0, 0.0, alpha)
    overlay_u8 = (np.clip(overlay, 0.0, 1.0) * 255).astype(np.uint8)
    png_file_path = os.path.join(output_dir, png_file_name)
    image = Image.fromarray(overlay_u8, mode="RGBA")
    image.save(png_file_path)
    return overlay


def is_docker_running():
    import docker
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False
    

def is_path_docker_compatible(path):
    return not ' ' in path


def to_unix_path(path):
    return path.replace("\\", "/").replace(" ", "\\ ")