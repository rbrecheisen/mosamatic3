import click
import textwrap


def help_command(cli_group: click.Group) -> click.Command:
    @click.command(name="help", help="Show docstrings for commands, e.g., `mosamatic help dcm2png`.")
    @click.argument("command_name", required=False)
    def help(command_name):
        commands = cli_group.commands
        if command_name:
            cmd = commands.get(command_name)
            if cmd and hasattr(cmd, 'callback') and cmd.callback.__doc__:
                print()
                print(textwrap.dedent(cmd.callback.__doc__).strip())
            else:
                click.echo(f'No docstring found for command: {command_name}')
        else:
            click.echo('Available commands with docstrings:')
            for name, cmd in commands.items():
                if hasattr(cmd, 'callback') and cmd.callback.__doc__:
                    click.echo(f"  {name}")
            click.echo('\nUse: `mosamatic show-doc <command>` to view a commands docstring')
    return help
