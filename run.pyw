import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))

from kato.main import main  # noqa: E402

if __name__ == "__main__":
    main()
