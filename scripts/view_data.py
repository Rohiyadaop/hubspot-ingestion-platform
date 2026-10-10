from pathlib import Path
import sys
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data" / "parquet" / "hubspot_data"

resource = sys.argv[1] if len(sys.argv) > 1 else "contacts"
resource_dir = DATA_DIR / resource
files = sorted(resource_dir.glob("*.parquet"))

if not files:
    print(f"No Parquet files found for: {resource}")
    sys.exit(1)

df = pd.concat(
    [pd.read_parquet(file) for file in files],
    ignore_index=True,
)

print(f"Resource: {resource}")
print(f"Rows before deduplication: {len(df)}")

if "id" in df.columns:
    df = df.drop_duplicates(subset=["id"], keep="last")

print(f"Unique records by ID: {len(df)}")
print(f"Duplicate IDs removed from preview: {len(pd.concat([pd.read_parquet(file) for file in files], ignore_index=True)) - len(df)}")

print("\nData preview:")
print(df.head(20).to_string(index=False))

csv_path = PROJECT_DIR / "data" / f"preview_{resource}.csv"
df.to_csv(csv_path, index=False)
print(f"\nDeduplicated preview CSV saved to: {csv_path}")