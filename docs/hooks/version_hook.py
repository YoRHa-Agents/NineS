import re
from pathlib import Path


def define_env(env):
    """Define variables for mkdocs-macros."""
    version = "unknown"
    init_path = Path("src/nines/__init__.py")
    if init_path.exists():
        content = init_path.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            version = match.group(1)
    env.variables["nines_version"] = version
    env.variables["project_name"] = "NineS"
