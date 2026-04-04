import fnmatch
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

# =========================
# LOAD CONFIG
# =========================
CONFIG_PATH = "scope_config.yaml"

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

INCLUDE_DIRS = config["include_dirs"]
INCLUDE_FILES = set(config["include_files"])
INCLUDE_EXT = config["include_extensions"]
FORCE_INCLUDE = set(config.get("force_include", []))

EXCLUDE_FILES = set(config["exclude"]["files"])
EXCLUDE_PATTERNS = config["exclude"]["patterns"]
EXCLUDE_DIRS = config["exclude"]["directories"]

# =========================
# TIME (Berlin)
# =========================
def get_berlin_time():
    return datetime.now(ZoneInfo("Europe/Berlin"))

def format_timestamp(dt):
    return dt.strftime("%Y-%m-%d_%H-%M-%S")  # safe for filename

def human_time(dt):
    return dt.strftime("%A, %d %B %Y, %H:%M:%S (%Z)")

# =========================
# HELPERS
# =========================

def is_excluded(path: Path):
    if path.name in EXCLUDE_FILES:
        return True

    for d in EXCLUDE_DIRS:
        if d.strip("/") in path.parts:
            return True

    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(path.name, pattern):
            return True

    return False


def is_included_extension(path: Path):
    return any(fnmatch.fnmatch(path.name, ext) for ext in INCLUDE_EXT)


def count_words(text):
    return len(text.split())

# =========================
# MAIN LOGIC
# =========================

def collect_files_and_stats(root="."):
    collected_files = set()
    visited_dirs = set()

    # FORCE INCLUDE
    for file_path in FORCE_INCLUDE:
        p = Path(root) / file_path
        if p.exists():
            collected_files.add(p.resolve())

    # INCLUDE DIRS
    for dir_path in INCLUDE_DIRS:
        full_dir = Path(root) / dir_path
        if not full_dir.exists():
            continue

        for path in full_dir.rglob("*"):
            if path.is_dir():
                visited_dirs.add(path.resolve())

            if path.is_file():

                if str(path.relative_to(root)) not in FORCE_INCLUDE:
                    if is_excluded(path):
                        continue

                if is_included_extension(path):
                    collected_files.add(path.resolve())

    # INCLUDE FILES
    for file_path in INCLUDE_FILES:
        p = Path(root) / file_path
        if p.exists():
            if str(file_path) in FORCE_INCLUDE:
                collected_files.add(p.resolve())
            elif not is_excluded(p):
                collected_files.add(p.resolve())

    return sorted(collected_files), visited_dirs


def write_output(files, output_file):
    total_words = 0

    with open(output_file, "w", encoding="utf-8") as out:
        for file_path in files:
            relative_path = file_path.relative_to(Path(".").resolve())

            out.write(f"\n\n# FILE: {relative_path}\n\n")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    total_words += count_words(content)

                    if file_path.suffix == ".py":
                        out.write("```python\n")
                    else:
                        out.write("```\n")

                    out.write(content)
                    out.write("\n```\n")

            except Exception as e:
                out.write(f"[ERROR READING FILE: {e}]\n")

    return total_words


# =========================
# EXECUTION
# =========================

if __name__ == "__main__":
    start_time = time.time()
    berlin_now = get_berlin_time()

    filename_timestamp = format_timestamp(berlin_now)
    human_timestamp = human_time(berlin_now)

    output_file = f"repo_dump_{filename_timestamp}.md"

    files, dirs = collect_files_and_stats()
    total_words = write_output(files, output_file)

    end_time = time.time()

    # TERMINAL OUTPUT ONLY
    print("\n========== SUMMARY ==========")
    print(f"Run time (Berlin): {human_timestamp}")
    print(f"Output file: {output_file}")
    print(f"Total files processed: {len(files)}")
    print(f"Total folders scanned: {len(dirs)}")
    print(f"Total words: {total_words}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")