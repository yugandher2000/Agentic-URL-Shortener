"""
Maven test runner.
Executes `mvn test` in the Spring Boot project directory and returns
the raw stdout/stderr + return code for the Testing Agent to parse.
"""
from __future__ import annotations

import shutil
import subprocess

import config


def run_maven_tests(timeout_seconds: int = 180) -> dict:
    """
    Run `mvn test` and return:
        {stdout, stderr, return_code}

    If the `mvn` executable is not on PATH, returns a synthetic failure
    so the graph can handle it gracefully rather than crashing.
    """
    mvn_cmd = shutil.which("mvn") or "mvn"

    try:
        proc = subprocess.run(
            [mvn_cmd, "test", "--no-transfer-progress",
             "-f", str(config.SPRING_PROJECT_PATH / "pom.xml")],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "stdout":      proc.stdout,
            "stderr":      proc.stderr,
            "return_code": proc.returncode,
        }
    except FileNotFoundError:
        return {
            "stdout":      "",
            "stderr":      "mvn not found on PATH. Install Maven and re-run.",
            "return_code": 127,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout":      "",
            "stderr":      f"mvn test timed out after {timeout_seconds}s.",
            "return_code": -1,
        }
