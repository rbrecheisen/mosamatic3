import click


@click.command(help='Auto-segment muscle and fat regions in DICOM images')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Directory containing DICOM images',
)
@click.option(
    '--model-dir',
    '-m',
    required=True,
    help='Directory containing AI model files',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save NumPy segmentation files',
)
def segment(input_dir, model_dir, output_dir):
    """
    Auto-segment muscle and fat regions in DICOM images. Three tissue comparments are
    segmented: (1) muscle, (2) visceral fat, and (3) subcutaneous fat. Muscle will have
    the label "1", visceral fat the label "5" and subcutaneous fat the label "7". 
    Background will be label "0". Each pixel in the output NumPy segmentation file will
    have one label assigned to it depending on its tissue class (0, 1, 5 or 7).

    The model directory specifies which AI segmentation model to use. Currently, we have
    a L3 and T4 model. 
    
    Parameters:
    --input-dir : str
        Directory containing DICOM images.
    --model-dir : str
        Directory containing AI model files (either L3 or T4).
    --output-dir : str
        Directory to save NumPy segmentation files.

    Examples:
        mosamatic3 segment -i /path/to/dicom -m /path/to/model -o /path/to/numpy
    """
    print(f'Running segmentation on DICOM images in {input_dir}, using AI model in {model_dir} and saving output NumPy segmentations in {output_dir}')