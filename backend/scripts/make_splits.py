from pathlib import Path
from collections import defaultdict
import hashlib
import json
import random

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "plantvillage"
IMAGE_ROOT = DATA_ROOT / "all"
OUTPUT = DATA_ROOT.parent / "splits.json"
SEED = 42
EXTENSIONS = {".jpg", ".jpeg", ".png"}

if not IMAGE_ROOT.exists():
    raise SystemExit(f"Dataset not found: {IMAGE_ROOT}")

if OUTPUT.exists():
    raise SystemExit(f"STOP: {OUTPUT} already exists. Nothing overwritten.")

classes = sorted(p for p in IMAGE_ROOT.iterdir() if p.is_dir())
if len(classes) != 38:
    raise SystemExit(f"Expected 38 classes, found {len(classes)}")

hash_groups = defaultdict(list)
hash_labels = defaultdict(set)

print("Scanning images and checking exact duplicates...")

for folder in classes:
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    )

    if not files:
        raise SystemExit(f"Empty class: {folder.name}")

    for index, path in enumerate(files, 1):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(DATA_ROOT).as_posix()
        hash_groups[(folder.name, digest)].append(relative)
        hash_labels[digest].add(folder.name)

    print(f"Checked {folder.name}: {len(files)} images")

cross_class = {
    digest: labels
    for digest, labels in hash_labels.items()
    if len(labels) > 1
}
if cross_class:
    raise SystemExit(
        f"STOP: {len(cross_class)} identical images have conflicting labels. "
        "Review these before splitting."
    )

rng = random.Random(SEED)
splits = {"train": [], "val": [], "test": []}
class_summary = {}

for folder in classes:
    groups = [
        paths
        for (class_name, digest), paths in hash_groups.items()
        if class_name == folder.name
    ]
    rng.shuffle(groups)

    n = len(groups)
    if n < 3:
        raise SystemExit(f"Not enough unique images in {folder.name}")

    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    n_test = n - n_train - n_val

    if min(n_train, n_val, n_test) < 1:
        raise SystemExit(f"Invalid split size for {folder.name}")

    assignments = [
        ("train", groups[:n_train]),
        ("val", groups[n_train:n_train + n_val]),
        ("test", groups[n_train + n_val:])
    ]

    for split_name, selected_groups in assignments:
        for group in selected_groups:
            splits[split_name].extend(group)

    class_summary[folder.name] = {
        name: sum(len(group) for group in selected)
        for name, selected in assignments
    }

payload = {
    "seed": SEED,
    "method": "stratified class split; exact SHA256 duplicates kept together",
    "splits": splits,
    "class_summary": class_summary
}

temporary = OUTPUT.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
temporary.replace(OUTPUT)

print("\nDataset split completed.")
print("Classes:", len(classes))
print("Images:", sum(len(v) for v in splits.values()))
print("Unique image groups:", len(hash_groups))
print("Exact duplicate copies:", sum(len(v) - 1 for v in hash_groups.values()))
print("Training:", len(splits["train"]))
print("Validation:", len(splits["val"]))
print("Testing:", len(splits["test"]))
print("Manifest:", OUTPUT)
