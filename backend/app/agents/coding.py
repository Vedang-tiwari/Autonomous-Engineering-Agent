import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.core.llm import BaseLLM
from app.core.security import SecurityManager
from app.services.tools import RepositoryTools

class CodingAgent:
    """
    Diagnoses bugs, reasons on code modifications, applies patches or creates new files,
    and adds regression test assertions.
    """

    def __init__(self, repo_dir: Path, tools: RepositoryTools, llm: BaseLLM):
        self.repo_dir = repo_dir
        self.tools = tools
        self.llm = llm

    async def diagnose_and_fix(
        self,
        task_goal: str,
        relevant_chunks: List[Dict[str, Any]],
        test_failure_context: Optional[str] = None,
        previous_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Formulates a diagnosis and generates targeted file updates to solve the task.
        """
        system_prompt = (
            "You are the Expert Autonomous Coding Agent. Your job is to analyze the task, "
            "review the retrieved code context and test failures, identify the root cause, "
            "and produce exact code modifications. Always include regression assertions."
        )

        context_str = ""
        for c in relevant_chunks:
            escaped_code = SecurityManager.sanitize_untrusted_content(c['content'], label=f"FILE_{c['file_path']}")
            context_str += f"\n--- File: {c['file_path']} (lines {c['start_line']}-{c['end_line']}) ---\n{escaped_code}\n"

        prompt = f"""Task Goal:
{task_goal}

Relevant Code Context:
{context_str}

Test Failure Context:
{test_failure_context or 'No prior test failures recorded. Baseline verification.'}

Reviewer / Iteration Feedback:
{previous_feedback or 'First implementation attempt.'}

Instructions:
1. Explain the root cause of the issue or requirement.
2. Provide precise modifications in a JSON structure:
{{
    "root_cause": "Detailed explanation of why the bug happens",
    "solution_strategy": "Steps taken to resolve",
    "modifications": [
        {{
            "file_path": "path/to/file.py",
            "action": "modify",  // "modify" or "create"
            "old_str": "exact string to replace",
            "new_str": "replacement string",
            "full_content": "optional full content if creating or rewriting file"
        }}
    ]
}}
"""

        try:
            res = await self.llm.generate_json(prompt, system_prompt=system_prompt)
            modifications = res.get("modifications", [])
            applied_results = []

            for mod in modifications:
                file_path = mod.get("file_path")
                if not file_path:
                    continue

                if mod.get("action") == "modify" and mod.get("old_str") and mod.get("new_str"):
                    patch_res = self.tools.apply_patch(file_path, mod["old_str"], mod["new_str"])
                    if not patch_res.get("success"):
                        # If string patch fails, fallback to full write if provided
                        if mod.get("full_content"):
                            patch_res = self.tools.write_file(file_path, mod["full_content"])
                    applied_results.append(patch_res)
                elif mod.get("full_content"):
                    write_res = self.tools.write_file(file_path, mod["full_content"])
                    applied_results.append(write_res)

            return {
                "success": True,
                "root_cause": res.get("root_cause", "Applied corrective patch according to task goal."),
                "solution_strategy": res.get("solution_strategy", "Localized modifications with regression coverage."),
                "applied_results": applied_results
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "root_cause": "Failed to generate structured patch.",
                "solution_strategy": "Manual fallback required.",
                "applied_results": []
            }
