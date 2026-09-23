import shutil
import subprocess
from pathlib import Path

import pytest


def test_narrative_module_parses_on_python_311():
    python = shutil.which("python3.11")
    if not python:
        pytest.skip("Python 3.11 is not installed")
    source = Path(__file__).resolve().parents[1] / "app" / "narrative.py"
    code = "from pathlib import Path; p=Path(r'%s'); compile(p.read_text(), str(p), 'exec')" % source
    result = subprocess.run([python, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
