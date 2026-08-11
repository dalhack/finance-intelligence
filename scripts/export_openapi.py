import json
from pathlib import Path

from app.main import app


def main():
    openapi_data = app.openapi()
    contracts_dir = Path("contracts")
    contracts_dir.mkdir(exist_ok=True)
    out_file = contracts_dir / "openapi_spec.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2, sort_keys=True)
    print(f"Exported OpenAPI spec to {out_file}")


if __name__ == "__main__":
    main()
