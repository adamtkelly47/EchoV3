import sys
from pathlib import Path

# Makes `apps.*` and `scripts.*` importable regardless of invocation cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
