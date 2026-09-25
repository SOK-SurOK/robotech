import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "modules" / "m2_camera"))
sys.path.insert(0, str(REPO_ROOT / "modules" / "m1_api"))
