from src.utils import clip

RAW_PATH = "data/raw.csv"
OUT_PATH = "outputs/processed.csv"
SCALE = 1000.0


def load_and_scale(path: str = RAW_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            x = float(parts[0]) / SCALE
            rows.append((x, parts[1]))
    return rows


def write_processed(rows, path: str = OUT_PATH):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("value,label\n")
        for x, label in rows:
            fh.write(f"{clip(x):.4f},{label}\n")


def main():
    rows = load_and_scale()
    write_processed(rows)


if __name__ == "__main__":
    main()
