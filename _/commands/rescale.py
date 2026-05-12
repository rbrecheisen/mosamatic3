import click


@click.command(help='Rescale non-square DICOM images to given size (default: 512)')
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
    '--size',
    '-s',
    default=512,
    type=int,
    required=True,
    help='Number of pixels for both rows and colums (must be square)',
)
def rescale(input_dir, output_dir, size):
    """
    Rescale non-square DICOM images to given size where the number of rows is <size> and
    the number of colums is <size>. Can be used to rescale DICOM images that are non-square
    for some reason, e.g., with obese patients where the number of columns in often larger
    than the number of rows. Mosamatic3 cannot handle non-square images. Furthermore, the
    images should be 512 x 512, so "512"" is the default size.
    
    Parameters:
    --input-dir : str
        Directory containing DICOM images.
    --output-dir : str
        Directory to save pipeline output. Each step in the pipeline will result in its own
        output sub-directory.
    --size : int
        Size of the output image. The default value is "512" so both the rows and columns of
        the new image will be 512 pixels. For segmentation of either L3 or T4 images, the size
        must be 512. 

    Examples:
        mosamatic3 rescale -i /path/to/dicom -o /path/to/output -s 512
    """
    print(f'Rescaling DICOM images in {input_dir} to size {size} x {size}')