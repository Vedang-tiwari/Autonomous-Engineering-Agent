from typing import Dict, Any, Optional
from app.sandbox.manager import SandboxManager
from app.schemas.task import TestResult

class TestingAgent:
    __test__ = False

    """
    Executes tests, linter checks, and builds inside the isolated sandbox.
    Analyzes failures and formats actionable debugging feedback.
    """

    def __init__(self, sandbox: SandboxManager):
        self.sandbox = sandbox

    async def run_validation(self, custom_test_command: Optional[str] = None) -> TestResult:
        """Runs the validation test suite inside sandbox."""
        return await self.sandbox.run_tests(test_command=custom_test_command)

    def extract_failure_context(self, test_result: TestResult) -> str:
        """Summarizes failing tests into concise context for the Coding Agent."""
        if test_result.passed:
            return "All tests passed successfully."

        summary = f"Command: {test_result.command} failed with exit code {test_result.exit_code}.\n"
        if test_result.failures_summary:
            summary += "Failures Summary:\n" + "\n".join(f"- {f}" for f in test_result.failures_summary)
        else:
            # Take last 30 lines of stderr or stdout
            raw = (test_result.stderr or test_result.stdout).splitlines()
            summary += "Tail Output:\n" + "\n".join(raw[-25:])

        return summary
