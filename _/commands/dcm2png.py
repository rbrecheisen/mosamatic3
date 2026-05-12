import click


@click.command(help='Convert DICOM files to PNG format')
@click.option(
    '--input-dir', 
    '-i', 
    required=True, 
    help='Directory containing DICOM files',
)
@click.option(
    '--output-dir', 
    '-o', 
    required=True, 
    help='Directory to save PNG files',
)
@click.option(
    '--fig-width', 
    '-w', 
    type=int, 
    default=10, 
    help='Figure width (default: 10)',
)
@click.option(
    '--fig-height', 
    '-h', 
    type=int, 
    default=10, 
    help='Figure height (default: 10)',
)
def dcm2png(input_dir, output_dir, fig_width, fig_height):
    """
    Convert DICOM files to PNG format. This only works for single DICOM images, not full scans.
    The PNG images have a default size of (10, 10).
    
    Parameters:
    --input-dir : str
        Directory containing DICOM files.
    --output-dir : str
        Directory to save PNG files.
    --fig-width : int
        Figure width (default: 10).
    --fig-height : int
        Figure height (default: 10).

    Examples:
        mosamatic3 dcm2png -i /path/to/dicom -o /path/to/png --fig-width 12 --fig-height 12
    """
    print(f'Converting DICOM files from {input_dir} to PNG format in {output_dir} with figure size {fig_width} x {fig_height}.')