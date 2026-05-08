import click


@click.command(help='Convert NIFTI segmentation files to NumPy format')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Directory containing NIFTI segmentation files',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save NumPy files',
)
def nii2seg(input_dir, output_dir):
    """
    Convert NIFTI segmentation files to NumPy format. The output NumPy files will be named
    by replacing the .nii or .nii.gz extension with .npy
    
    Parameters:
    --input-dir : str
        Directory containing NIFTI segmentation files.
    --output-dir : str
        Directory to save NumPy files.

    Examples:
        mosamatic3 pipeline -i /path/to/nifti -o /path/to/numpy
    """
    print(f'Converting DICOM files in {input_dir} to NumPy format in {output_dir}')