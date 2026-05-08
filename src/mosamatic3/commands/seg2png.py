import click


@click.command(help='Convert NumPy segmentation files to PNG format')
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
    help='Directory to save PNG images',
)
def seg2png(input_dir, output_dir):
    """
    Convert NumPy segmentations files (that are the output of mosamatic3 segment) and save
    them to PNG format in the output directory.
    
    Parameters:
    --input-dir : str
        Directory containing NumPy segmentation files.
    --output-dir : str
        Directory to save PNG images.

    Examples:
        mosamatic3 seg2png -i /path/to/numpy -o /path/to/png
    """
    print(f'Converting NumPy segmentation files in {input_dir} and saving to PNG format in {output_dir}')