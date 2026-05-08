import click


@click.command(help='Convert NumPy segmentation files to NIFTI format')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Directory containing NumPy segmentation files',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save NIFTI segmentation files',
)
def seg2nii(input_dir, output_dir):
    """
    Convert NumPy segmentations files (that are the output of mosamatic3 segment) and save
    them as NIFTI files in the output directory.
    
    Parameters:
    --input-dir : str
        Directory containing NumPy segmentation files.
    --output-dir : str
        Directory to save NIFTI segmentation files.

    Examples:
        mosamatic3 seg2nii -i /path/to/numpy -o /path/to/nifti
    """
    print(f'Converting NumPy segmentation files in {input_dir} and saving to NIFTI format in {output_dir}')