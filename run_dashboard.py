"""Start the Streamlit dashboard from any working directory."""

import subprocess
import sys
from pathlib import Path


def main():
    app = Path(__file__).resolve().parent / "web" / "app.py"
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app),
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            *sys.argv[1:],
        ],
        cwd=app.parent.parent,
    )


if __name__ == "__main__":
    raise SystemExit(main())
