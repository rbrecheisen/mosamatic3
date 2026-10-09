from pathlib import Path
import sys

def folder_size(folder):
    total = 0
    for file in folder.rglob("*"):
        try:
            if file.is_file():
                total += file.stat().st_size
        except (OSError, PermissionError):
            pass
    return total

def main():
    project_file = Path(sys.argv[1])
    total_bytes = 0

    for line in project_file.read_text(encoding="utf-8-sig").splitlines():
        path = line.strip().strip('"')

        if not path or path.startswith("#"):
            continue

        folder = Path(path)

        if not folder.is_dir():
            print(f"NOT FOUND: {folder}")
            continue

        size = folder_size(folder)
        total_bytes += size

        print(f"{size / 1024**2:12,.2f} MB  {folder}")

    print("-" * 70)
    print(f"TOTAL: {total_bytes / 1024**2:,.2f} MB")
    print(f"       {total_bytes / 1024**3:,.2f} GB")

if __name__ == "__main__":
    main()