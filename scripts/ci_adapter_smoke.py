"""Run synthetic adapter tests and expose bounded CI failure details as annotations."""

import subprocess
import sys


def main():
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_adapter_trace.py", "-v"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    print(completed.stdout, end="", flush=True)
    print(completed.stderr, end="", file=sys.stderr, flush=True)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-2800:]
        detail = detail.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::error title=Synthetic adapter smoke failed::" + detail, flush=True)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
