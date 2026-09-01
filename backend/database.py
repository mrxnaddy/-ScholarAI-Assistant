import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "opportunities.json"

def load_opportunities():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Data file not found at: '{DATA_FILE}'."
        )

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def get_all_opportunities():
    return load_opportunities()