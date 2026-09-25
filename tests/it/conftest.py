import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# m1_api первым: оба модуля содержат main.py, в тестах нужен main из m1_api
sys.path.insert(0, str(REPO_ROOT / "modules" / "m2_camera"))
sys.path.insert(0, str(REPO_ROOT / "modules" / "m1_api"))
