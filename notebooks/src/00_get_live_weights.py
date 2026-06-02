# %%
import sys
from pathlib import Path

_root = Path.cwd()
while not (_root / "notebooks" / "analysis").is_dir() and _root != _root.parent:
    _root = _root.parent
for _p in (_root, _root / "notebooks"):
    sys.path.insert(0, str(_p))

from aperiodic import get_live_weights

from analysis.utils import get_env

APERIODIC_API_KEY = get_env("APERIODIC_API_KEY")
portfolio = "momentum_enhanced.20"

live_weights = get_live_weights(id=portfolio, api_key=APERIODIC_API_KEY)
print(live_weights)
