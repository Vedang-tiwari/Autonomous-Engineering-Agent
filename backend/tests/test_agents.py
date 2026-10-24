import asyncio
import tempfile
import pytest
from pathlib import Path

from app.core.llm import MockLLM
from app.services.tools import RepositoryTools
from app.sandbox.manager import SandboxManager
from app.vector_db.retriever import CodeRetriever
from app.agents.planner import PlannerAgent
from app.agents.repository import RepositoryAgent
from app.agents.coding import CodingAgent
from app.agents.testing import TestingAgent
from app.agents.review import ReviewAgent
from app.schemas.task import TestResult

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)
        # Create a sample repository structure
        src_dir = repo_path / "src"
        src_dir.mkdir()
        (src_dir / "auth.py").write_text("def verify_jwt(token):\n    return token == 'valid_token'\n")
        (repo_path / "README.md").write_text("# Sample Project\nAuthentication service implementation.")
        (repo_path / "requirements.txt").write_text("pytest\n")
        
        tests_dir = repo_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_auth.py").write_text("from src.auth import verify_jwt\ndef test_jwt():\n    assert verify_jwt('valid_token') is True\n")
        
        yield repo_path

def test_planner_agent(temp_repo):
    async def _run():
        llm = MockLLM()
        planner = PlannerAgent(llm)
        plan = await planner.create_plan("Sample Python Repository", "Fix JWT authentication validation")
        assert plan is not None
        assert len(plan.steps) >= 5
        assert plan.steps[0].title != ""
    asyncio.run(_run())

def test_repository_agent(temp_repo):
    async def _run():
        tools = RepositoryTools(temp_repo)
        repo_agent = RepositoryAgent(temp_repo, tools)
        analysis = await repo_agent.analyze()
        assert analysis["tech_stack"]["language"] == "Python"
        assert "src" in analysis["directories"]
    asyncio.run(_run())

def test_code_retriever(temp_repo):
    retriever = CodeRetriever(temp_repo)
    retriever.index_repository()
    results = retriever.retrieve("verify_jwt token authentication", top_k=3)
    assert len(results) > 0
    assert any("auth.py" in r["file_path"] for r in results)

def test_tools_read_write(temp_repo):
    tools = RepositoryTools(temp_repo)
    read_res = tools.read_file("src/auth.py")
    assert read_res["success"] is True
    assert "verify_jwt" in read_res["content"]

    # Test patch
    patch_res = tools.apply_patch("src/auth.py", "return token == 'valid_token'", "return bool(token and token.startswith('bearer_'))")
    assert patch_res["success"] is True

    # Validate change
    updated = tools.read_file("src/auth.py")
    assert "bearer_" in updated["content"]

def test_sandbox_execution(temp_repo):
    async def _run():
        sandbox = SandboxManager(temp_repo)
        exit_code, stdout, stderr, duration = await sandbox.execute_command("python -c \"print('Sandbox active')\"")
        assert exit_code == 0
        assert "Sandbox active" in stdout
    asyncio.run(_run())

def test_review_agent():
    async def _run():
        llm = MockLLM()
        reviewer = ReviewAgent(llm)
        dummy_test = TestResult(command="pytest", exit_code=0, passed=True, total_tests=5, passed_tests=5, failed_tests=0)
        review_res = await reviewer.review("Fix JWT validation", "+ return token.is_valid()", dummy_test)
        assert review_res.decision == "APPROVED"
        assert review_res.quality_score >= 80
    asyncio.run(_run())
