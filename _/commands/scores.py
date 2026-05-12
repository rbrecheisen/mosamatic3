import click


@click.command(help='Calculate body composition scores using DICOM images and corresponding segmentations')
@click.option(
    '--images-dir', 
    '-i', 
    required=True, 
    help='Directory containing DICOM images',
)
@click.option(
    '--segmentations-dir', 
    '-s', 
    required=True, 
    help='Directory containing NumPy segmentation files (.npy extension)',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save scores (both .csv and .xlsx)',
)
def scores(input_dir, segmentations_dir, output_dir):
    """
    Calculate body composition scores from given DICOM images and corresponding segmentation files. 
    Each DICOM image is matched to its corresponding segmentation file based on its name. If the 
    segmentation file name contains the basename of the DICOM file, it is considered to match. E.g., 
    "P00001" for a DICOM file named "P00001.dcm" will be matched to a segmentation file that is 
    named "P00001.npy" or "P00001.seg.npy".

    The scores are saved both to CSV format (bc_scores.csv) and Excel format "bc_scores.xlsx".
    
    Parameters:
    --input-dir : str
        Directory containing DICOM images.
    --segmentations-dir : str
        Directory containing NumPy segmentation files with .npy extension.
    --output-dir : str
        Directory to save scores in CSV and Excel format.

    Examples:
        mosamatic3 scores -i /path/to/dicom -s /path/to/numpy -o /path/to/scores
    """
    print(f'Calculating body composition scores for DICOM images in {input_dir} and segmentation files in {segmentations_dir}, and saving to {output_dir}')