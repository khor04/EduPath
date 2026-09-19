"""
Builds career_mapping/edupath_mapping_evaluation.zip, the file uploaded to Google
Colab for career_mapping/edupath_mapping_evaluation.ipynb.

The notebook expects data/mapping_eval/method_outputs/, while the repo keeps
that folder as data/mapping_eval/PRIVATE_do_not_share/ (its name from the
blind-labelling phase), so the folder is renamed inside the zip.

Run after the final mapping run (works from any working directory):
    python career_mapping/scripts/build_notebook_zip.py
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the career_mapping/ folder
OUT = os.path.join(ROOT, "edupath_mapping_evaluation.zip")
RENAME = {"data/mapping_eval/PRIVATE_do_not_share/": "data/mapping_eval/method_outputs/"}
SKIP_SUFFIXES = (".tmp", ".log")


def archive_name(path):
    name = os.path.relpath(path, ROOT).replace(os.sep, "/")
    for old, new in RENAME.items():
        if name.startswith(old):
            return new + name[len(old):]
    return name


def main():
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(os.path.join(ROOT, "data")):
            for f in sorted(files):
                if f.startswith("~$") or f.endswith(SKIP_SUFFIXES):   # Excel lock files, temp files, logs
                    continue
                path = os.path.join(root, f)
                z.write(path, archive_name(path))
                count += 1
    print(f"{OUT}: {count} files, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
