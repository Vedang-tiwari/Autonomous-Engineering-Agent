import re
import time
from typing import Optional
from app.services.git_service import GitService
from app.schemas.task import PullRequestInfo

class GitAgent:
    """
    Automates git branching, commits, and Pull Request preparation.
    """

    def __init__(self, git_service: GitService):
        self.git_service = git_service

    def prepare_branch(self, task_goal: str) -> str:
        """Derives a clean branch name and switches to it."""
        clean_name = re.sub(r'[^a-zA-Z0-9]+', '-', task_goal.lower()).strip('-')[:35]
        branch_name = f"agent/{clean_name}-{int(time.time()) % 10000}"
        self.git_service.create_branch(branch_name)
        return branch_name

    def commit_changes(self, task_goal: str) -> Optional[str]:
        """Creates a conventional commit for the changes."""
        msg = f"fix(agent): {task_goal[:60]}"
        return self.git_service.commit_changes(msg)

    async def create_pull_request(
        self,
        task_id: str,
        task_goal: str,
        branch_name: str,
        commit_sha: Optional[str],
        test_summary: str,
        review_summary: str
    ) -> PullRequestInfo:
        """Assembles Pull Request description and registers completion."""
        return await self.git_service.create_pull_request(
            task_id=task_id,
            goal=task_goal,
            branch_name=branch_name,
            commit_sha=commit_sha,
            test_summary=test_summary,
            review_summary=review_summary
        )
