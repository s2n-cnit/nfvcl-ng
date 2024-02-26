import inspect
from pathlib import Path


def rel_path(file: str) -> Path:
    mod_path = Path(inspect.stack()[1].filename).parent
    return Path(mod_path, file)
