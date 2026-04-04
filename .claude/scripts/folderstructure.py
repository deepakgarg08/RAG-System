import os

OUTPUT_FILE = "project_structure.md"
MAX_DEPTH = 4


def get_structure(root_dir, depth=0):
    if depth > MAX_DEPTH:
        return []

    structure = []
    indent = "  " * depth

    try:
        items = sorted(os.listdir(root_dir))
    except PermissionError:
        return [f"{indent}- ⚠️ Permission Denied"]

    for item in items:
        if item.startswith('.'):
            continue

        path = os.path.join(root_dir, item)

        if os.path.isdir(path):
            structure.append(f"{indent}- 📁 {item}/")
            structure.extend(get_structure(path, depth + 1))
        else:
            structure.append(f"{indent}- 📄 {item}")

    return structure


def main():
    root_dir = os.getcwd()
    structure = get_structure(root_dir)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Project Structure (Up to 10 Levels)\n\n")
        f.write("\n".join(structure))

    print("✅ Structure generated!")
    print(f"📁 Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()