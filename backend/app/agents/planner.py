from typing import List, Dict, Any
from app.core.llm import BaseLLM
from app.schemas.task import ExecutionPlan, ExecutionPlanStep, StepStatus

class PlannerAgent:
    """
    Decomposes an engineering objective into a structured, step-by-step execution plan.
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def create_plan(self, repo_summary: str, task_goal: str) -> ExecutionPlan:
        system_prompt = (
            "You are the Lead Planning Agent in an Autonomous Engineering Agent system. "
            "Analyze the engineering objective and repository context, then output a structured plan "
            "with sequential steps needed to solve the task, verify the fix with tests, and prepare a PR."
        )

        prompt = f"""Task Goal: {task_goal}

Repository Summary:
{repo_summary}

Generate a JSON object with:
- "overview": High level description of the plan
- "steps": List of objects with "step_number", "title", and "description"
"""

        try:
            data = await self.llm.generate_json(prompt, system_prompt=system_prompt)
            steps = []
            for s in data.get("steps", []):
                steps.append(ExecutionPlanStep(
                    step_number=s.get("step_number", len(steps) + 1),
                    title=s.get("title", f"Step {len(steps) + 1}"),
                    description=s.get("description", ""),
                    status=StepStatus.PENDING
                ))
            overview = data.get("overview", f"Autonomous engineering plan for: {task_goal}")
            if not steps:
                steps = self._default_steps(task_goal)
            return ExecutionPlan(overview=overview, steps=steps)
        except Exception:
            return ExecutionPlan(
                overview=f"Autonomous plan for: {task_goal}",
                steps=self._default_steps(task_goal)
            )

    def _default_steps(self, task_goal: str) -> List[ExecutionPlanStep]:
        return [
            ExecutionPlanStep(step_number=1, title="Repository Analysis", description="Analyze codebase structure, entry points, and test framework."),
            ExecutionPlanStep(step_number=2, title="Relevant Code Retrieval", description="Retrieve files and functions related to the objective."),
            ExecutionPlanStep(step_number=3, title="Baseline Test Execution", description="Execute sandbox test suite to capture baseline or reproduce failure."),
            ExecutionPlanStep(step_number=4, title="Bug Diagnosis & Code Modification", description="Identify root cause, apply code changes, and add regression tests."),
            ExecutionPlanStep(step_number=5, title="Sandboxed Verification", description="Execute tests and linters in isolated sandbox to verify fixes."),
            ExecutionPlanStep(step_number=6, title="Automated Code Review", description="Review git diff for correctness, quality, and regression safety."),
            ExecutionPlanStep(step_number=7, title="Git Branch & Pull Request", description="Commit validated changes to an agent feature branch and prepare PR.")
        ]
