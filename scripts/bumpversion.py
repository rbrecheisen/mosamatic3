import argparse
import tomllib
import re
from pathlib import Path
from tomlkit import parse, dumps

PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def get_version(pyproject_file='pyproject.toml') -> str:
    path = Path(pyproject_file)
    with path.open('rb') as f:
        data = tomllib.load(f)
    return data['project']['version']


def set_version(new_version: str, pyproject_file='pyproject.toml') -> None:
    path = Path(pyproject_file)
    doc = parse(path.read_text(encoding='utf-8'))
    doc['project']['version'] = new_version
    path.write_text(dumps(doc), encoding='utf-8')
    with open('VERSION', 'w') as f:
        f.write(new_version)


def bump_version(version: str, part: str) -> str:
    m = PATTERN.match(version)
    if not m:
        raise ValueError(f'Version "{version}" not in major.minor.patch format')
    major, minor, patch = map(int, m.groups())
    if part == 'patch':
        patch += 1
    elif part == 'minor':
        patch = 0
        minor += 1
    elif part == 'major':
        patch = 0
        minor = 0
        major += 1
    else:
        raise ValueError(f'Argument "part" must be one of: major, minor, patch')
    return f'{major}.{minor}.{patch}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--part', help='One of: major, minor, patch', default='patch')
    parser.add_argument('--update_toml', help='Update pyproject.toml', type=int, default=0)
    args = parser.parse_args()
    version = get_version()
    new_version = bump_version(version, args.part)
    if args.update_toml == 1:
        set_version(new_version)


if __name__ == '__main__':
    main()