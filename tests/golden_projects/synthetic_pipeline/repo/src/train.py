from src.preprocess import load_and_scale, write_processed
from src.utils import safe_div
import pickle

MODEL_PATH = "outputs/model.pkl"
DATA_PATH = "outputs/processed.csv"


def read_processed(path: str = DATA_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            rows.append((float(parts[0]), parts[1]))
    return rows


def train_model(rows):
    mean = sum(x for x, _ in rows) / len(rows)
    return {"mean": mean, "n": len(rows), "spread": safe_div(max(x for x, _ in rows), mean)}


def main():
    rows = read_processed()
    model = train_model(rows)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)


if __name__ == "__main__":
    main()
