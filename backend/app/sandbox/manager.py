import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from app.core.config import settings
from app.core.security import SecurityManager
from app.schemas.task import TestResult

class SandboxManager:
    """
    Manages isolated execution of tests, linters, and verification scripts.
    Supports Docker container execution when Docker is active, and provides
    a secure timeout-enforced process sandbox with environment isolation.
    """

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir.resolve()
        self.timeout = settings.SANDBOX_TIMEOUT
        self.docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Check if Docker daemon is accessible."""
        docker_path = shutil.which("docker")
        if not docker_path:
            return False
        try:
            res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            return res.returncode == 0
        except Exception:
            return False

    async def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        custom_env: Optional[Dict[str, str]] = None
    ) -> Tuple[int, str, str, float]:
        """
        Executes a command inside the repository sandbox environment.
        Returns: (exit_code, stdout, stderr, duration_seconds)
        """
        effective_timeout = timeout or self.timeout
        start_time = time.time()

        if self.docker_available:
            return await self._run_in_docker(command, effective_timeout, custom_env)
        else:
            return await self._run_in_process(command, effective_timeout, custom_env)

    async def _run_in_docker(
        self,
        command: str,
        timeout: int,
        custom_env: Optional[Dict[str, str]] = None
    ) -> Tuple[int, str, str, float]:
        """Runs the command inside an isolated Docker container with volume mount."""
        start_time = time.time()
        container_name = f"agent_sandbox_{int(time.time() * 1000)}"
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "-m", settings.SANDBOX_MEMORY_LIMIT,
            "--cpus", "1.0",
            "-v", f"{self.repo_dir}:/workspace",
            "-w", "/workspace",
            "python:3.11-slim",
            "sh", "-c", command
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                duration = time.time() - start_time
                stdout = stdout_data.decode("utf-8", errors="replace")
                stderr = stderr_data.decode("utf-8", errors="replace")
                return proc.returncode or 0, SecurityManager.mask_credentials(stdout), SecurityManager.mask_credentials(stderr), duration
            except asyncio.TimeoutError:
                # Kill docker container
                subprocess.run(["docker", "kill", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return 124, "", f"Execution timed out after {timeout} seconds.", time.time() - start_time
        except Exception as e:
            # Fall back to process sandbox if Docker execution fails
            return await self._run_in_process(command, timeout, custom_env)

    async def _run_in_process(
        self,
        command: str,
        timeout: int,
        custom_env: Optional[Dict[str, str]] = None
    ) -> Tuple[int, str, str, float]:
        """Runs the command in a secured process environment with stripped secrets and timeout."""
        start_time = time.time()

        # Sanitize environment: keep only safe system environment variables
        safe_env_keys = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOMEPATH", "USERPROFILE", "LANG", "LC_ALL"}
        sandboxed_env = {k: v for k, v in os.environ.items() if k.upper() in safe_env_keys}
        sandboxed_env["PYTHONPATH"] = str(self.repo_dir)
        sandboxed_env["CI"] = "true"
        if custom_env:
            sandboxed_env.update(custom_env)

        try:
            # Use shell execution for command parsing
            is_win = os.name == "nt"
            shell_cmd = command

            proc = await asyncio.create_subprocess_shell(
                shell_cmd,
                cwd=str(self.repo_dir),
                env=sandboxed_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                duration = time.time() - start_time
                stdout = stdout_data.decode("utf-8", errors="replace")
                stderr = stderr_data.decode("utf-8", errors="replace")
                return proc.returncode or 0, SecurityManager.mask_credentials(stdout), SecurityManager.mask_credentials(stderr), duration
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return 124, "", f"Execution timed out after {timeout} seconds.", time.time() - start_time
        except Exception as e:
            duration = time.time() - start_time
            return 1, "", f"Process execution error: {str(e)}", duration

    async def run_tests(self, test_command: Optional[str] = None) -> TestResult:
        """
        Runs tests and parses the results into a standardized TestResult.
        Auto-detects test command if none provided.
        """
        cmd = test_command or self.detect_test_command()
        exit_code, stdout, stderr, duration = await self.execute_command(cmd)

        passed = (exit_code == 0)
        parsed = self._parse_test_output(cmd, stdout, stderr)

        return TestResult(
            command=cmd,
            exit_code=exit_code,
            passed=passed,
            total_tests=parsed["total"],
            passed_tests=parsed["passed"],
            failed_tests=parsed["failed"],
            duration_seconds=round(duration, 2),
            stdout=stdout,
            stderr=stderr,
            failures_summary=parsed["failures"]
        )

    def detect_test_command(self) -> str:
        """Auto-detects appropriate test command based on repository manifests."""
        # Check Python
        if (self.repo_dir / "pytest.ini").exists() or (self.repo_dir / "pyproject.toml").exists() or any(self.repo_dir.glob("**/test_*.py")):
            return "python -m pytest"

        # Check Node.js
        if (self.repo_dir / "package.json").exists():
            return "npm test"

        # Check Rust
        if (self.repo_dir / "Cargo.toml").exists():
            return "cargo test"

        # Check Go
        if (self.repo_dir / "go.mod").exists():
            return "go test ./..."

        # Default fallback
        return "python -m unittest discover -s tests"

    def _parse_test_output(self, command: str, stdout: str, stderr: str) -> Dict[str, Any]:
        """Parses output from common test runners to extract counts and failures."""
        output = stdout + "\n" + stderr
        total = 0
        passed = 0
        failed = 0
        failures: List[str] = []

        # Pytest pattern: 'X passed, Y failed' or 'X passed' or 'Y failed'
        import re
        pytest_match = re.search(r'([0-9]+)\s+passed', output)
        if pytest_match:
            passed = int(pytest_match.group(1))

        failed_match = re.search(r'([0-9]+)\s+failed', output)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r'([0-9]+)\s+error', output)
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed

        # Extract failure lines
        for line in output.splitlines():
            line_str = line.strip()
            if line_str.startswith("FAILED ") or "AssertionError" in line_str or "Error:" in line_str:
                failures.append(line_str[:200])

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "failures": failures[:10]  # Cap to top 10
        }
