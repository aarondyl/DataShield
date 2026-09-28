"""Streamlit Cloud entrypoint; keep app.py as the application implementation."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
