import os
from pathlib import Path
import subprocess
import sys


def test_windowed_entrypoint_initializes_uvicorn_without_console(tmp_path):
    code = """
import runpy, sys
sys.stdout = None
sys.stderr = None
runpy.run_path('desktop_sidecar.py', run_name='windowed_smoke')
import uvicorn
uvicorn.Config('app.main:app')
assert sys.stdout is not None and sys.stderr is not None
assert not sys.stdout.isatty()
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1],
        env={**os.environ, "RUNTIME_MODE": "local", "LOCAL_DATA_DIR": str(tmp_path), "RUN_SEED": "false"},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
