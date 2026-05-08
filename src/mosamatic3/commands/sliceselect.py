import click


@click.command(help='Auto-select DICOM image from full CT scan at given vertebral level')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Root directory containing CT scans for each patient',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save select image files for the given vertebral level',
)
@click.option(
    '--vertebral-level',
    '-v',
    required=True,
    help='Vertebral level to analyze (loads appropriate AI model)',
)
def sliceselect(input_dir, output_dir, vertebral_level):
    """
    Auto select single DICOM images from full CT scans at the given vertebral level. Most
    stable selection target is "L3" but other levels should also work, e.g., "T4" or "T12".
    The input directory should contain sub-directories for each patient and named according
    to the patient ID (ideally). Inside each patient/scan directory the actual CT scan images
    can be located in a nested directory structure. 

    The output L3 image file (for each CT scan) will be named according to the format:
        <vertebral level>_<patient ID>.dcm
    
    If there are multiple CT scans per patient, the tool will select DICOM images for each CT
    scan but update the output (selected) image file name according the format:
        <vertebral level>_<patient ID>_<scan directory name>.dcm
    
    Parameters:
    --input-dir : str
        Directory containing DICOM images.
    --output-dir : str
        Directory to save NumPy segmentation files.
    --vertebral-level : str
        Vertebral level for selecting DICOM images. The middle slice going through the vertebral
        body will be selected.

    Examples:
        mosamatic3 sliceselect -i /path/to/scans -o /path/to/images -v L3
    """
    print(f'Running segmentation on DICOM images in {input_dir}, using AI model in {model_dir} and saving output NumPy segmentations in {output_dir}')