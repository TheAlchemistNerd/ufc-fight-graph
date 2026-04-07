"""
UFC Fight Graph - Dashboard Entry Point.

Usage:
    python run_dashboard.py
"""

import subprocess
import sys

def main():
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "web/app.py",
        "--server.headless", "true",
        "--server.port", "8501",
        "--server.address", "127.0.0.1",
        "--server.enableCORS", "false",
        "--browser.gatherUsageStats", "false",
    ])

if __name__ == "__main__":
    main()
