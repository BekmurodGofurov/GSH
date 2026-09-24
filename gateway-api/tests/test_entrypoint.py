"""The service must survive the entrypoint Docker actually uses.

`Dockerfile` runs `python main.py`, which loads the file as `__main__`.
Any module-level `import main` from a package that main itself imports
(app.agent.*) then re-executes main.py under a second module name and
dies with "partially initialized module ... circular import".

pytest cannot catch that on its own: it imports main as an ordinary
module, so the cycle closes harmlessly and every other test passes while
production crash-loops. This test shells out and reproduces the real
entrypoint instead.
"""

import os
import subprocess
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent


def _env_without_port() -> dict:
    """A clean environment for the child process, with no port set.

    Leaving PORT unset is deliberate: main.py finishes importing, then
    raises a clear ValueError instead of binding a socket, so the test
    exercises the whole import phase without leaving a server running.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PORT", "GATEWAY_PORT", "GATEWAY_CONTAINER_PORT")
    }
    env.update(
        {
            "DB_URL": "postgresql://user:pass@localhost:5432/game_monitor",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "admin",
            "FRONTEND_URL": "http://localhost:3000",
            "AGENT_LLM_API_KEY": "test-key-not-used",
        }
    )
    return env


def test_main_imports_cleanly_when_run_as_a_script():
    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=SERVICE_ROOT,
        env=_env_without_port(),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert "circular import" not in result.stderr, (
        "main.py cannot be run as a script -- something under app/ imports "
        f"main at module level:\n{result.stderr}"
    )
    assert "ImportError" not in result.stderr, result.stderr

    # Reaching the PORT check means every import above it succeeded.
    assert "PORT (or GATEWAY_PORT" in result.stderr, result.stderr
