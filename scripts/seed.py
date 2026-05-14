from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.content.registry import SEED_CONTENT


def main() -> None:
    for item in SEED_CONTENT:
        print(f"seed content: {item.slug}")


if __name__ == "__main__":
    main()
