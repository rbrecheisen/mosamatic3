import click


@click.command(help='Run default body composition pipeline on single DICOM images')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Directory containing DICOM images',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save NumPy files',
)
@click.option(
    '--vertebral-level',
    '-v',
    required=True,
    help='Vertebral level to analyze (loads appropriate AI model)',
)
def pipeline(input_dir, output_dir, vertebral_level):
    """
    Run default body composition pipeline on a set of single DICOM images. The pipeline
    will run (1) rescaling to 512x512, (2) segmentation of muscle and fat, (3) calculate
    body composition scores and (4) create PNG images of both DICOM images and segmentations.
    
    Parameters:
    --input-dir : str
        Directory containing DICOM images.
    --output-dir : str
        Directory to save pipeline output. Each step in the pipeline will result in its own
        output sub-directory.
    --vertebral-level : str
        Vertebral level to analyze (loads appropriate AI model). Allowed values are "L3" or "T4".

    Examples:
        mosamatic3 pipeline -i /path/to/dicom -o /path/to/output -v L3
    """
    print(f'Running pipeline on DICOM images in {input_dir} and saving output in {output_dir}. Using vertebral level {vertebral_level}')