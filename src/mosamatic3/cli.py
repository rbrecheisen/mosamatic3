import click
from mosamatic3.commands import (
    dcm2png,
    help,
    nii2seg,
    pipeline,
    rescale,
    scores,
    seg2nii,
    seg2png,
    segment,
    sliceselect,
)


class CustomHelpGroup(click.Group):
    def format_commands(self, ctx, formatter):
        commands = self.list_commands(ctx)
        with formatter.section('Commands'):
            for command_name in commands:
                command = self.get_command(ctx, command_name)
                if command is None or command.hidden:
                    continue
                help_text = command.get_short_help_str()
                formatter.write_text(f'{command_name:15} {help_text}')


@click.group(cls=CustomHelpGroup)
def main():
    pass


main.add_command(dcm2png.dcm2png)
main.add_command(help.help_command(main))
main.add_command(nii2seg.nii2seg)
main.add_command(pipeline.pipeline)
main.add_command(rescale.rescale)
main.add_command(scores.scores)
main.add_command(seg2nii.seg2nii)
main.add_command(seg2png.seg2png)
main.add_command(segment.segment)
main.add_command(sliceselect.sliceselect)