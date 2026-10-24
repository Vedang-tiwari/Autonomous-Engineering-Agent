import os
from pathlib import Path
from typing import Dict, List, Any
from app.services.tools import RepositoryTools

class RepositoryAgent:
    """
    Understands repository architecture, languages, framework conventions,
    dependencies, entry points, and test framework configuration.
    """

    def __init__(self, repo_dir: Path, tools: RepositoryTools):
        self.repo_dir = repo_dir
        self.tools = tools

    async def analyze(self) -> Dict[str, Any]:
        """Performs full static inspection of repository structure."""
        dir_res = self.tools.list_dir("")
        entries = dir_res.get("entries", [])

        # Detect primary language and build system
        files = [e["name"] for e in entries if not e["is_dir"]]
        dirs = [e["name"] for e in entries if e["is_dir"]]

        tech_stack = self._detect_tech_stack(files)
        test_info = self._detect_testing_framework(files, dirs)

        # Inspect README if available
        readme_snippet = ""
        for name in ["README.md", "README.txt", "readme.md"]:
            if name in files:
                read_res = self.tools.read_file(name, start_line=1, end_line=50)
                if read_res.get("success"):
                    readme_snippet = read_res["content"]
                break

        summary = (
            f"Repository Tech Stack: {tech_stack.get('language', 'Unknown')} ({tech_stack.get('framework', 'Generic')})\n"
            f"Test Runner: {test_info.get('runner', 'Unknown')}\n"
            f"Key Directories: {', '.join(dirs[:10])}\n"
            f"Key Config Files: {', '.join(tech_stack.get('config_files', []))}\n"
        )
        if readme_snippet:
            summary += f"\nREADME Preview:\n{readme_snippet[:300]}..."

        return {
            "tech_stack": tech_stack,
            "test_info": test_info,
            "directories": dirs,
            "files": files,
            "summary": summary
        }

    def _detect_tech_stack(self, files: List[str]) -> Dict[str, Any]:
        stack = {"language": "Unknown", "framework": "Generic", "config_files": []}

        if "pyproject.toml" in files or "requirements.txt" in files or "setup.py" in files:
            stack["language"] = "Python"
            stack["config_files"] = [f for f in files if f in {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}]
            if "manage.py" in files:
                stack["framework"] = "Django"
            elif any("fastapi" in f for f in files):
                stack["framework"] = "FastAPI"
            elif any("flask" in f for f in files):
                stack["framework"] = "Flask"

        elif "package.json" in files:
            stack["language"] = "JavaScript / TypeScript"
            stack["config_files"] = [f for f in files if f in {"package.json", "tsconfig.json", "webpack.config.js"}]
            if "next.config.js" in files or "next.config.mjs" in files:
                stack["framework"] = "Next.js"
            elif "vite.config.ts" in files or "vite.config.js" in files:
                stack["framework"] = "Vite"
            else:
                stack["framework"] = "Node.js"

        elif "Cargo.toml" in files:
            stack["language"] = "Rust"
            stack["config_files"] = ["Cargo.toml"]

        elif "go.mod" in files:
            stack["language"] = "Go"
            stack["config_files"] = ["go.mod"]

        return stack

    def _detect_testing_framework(self, files: List[str], dirs: List[str]) -> Dict[str, Any]:
        info = {"runner": "unknown", "test_dir": None}
        if "tests" in dirs:
            info["test_dir"] = "tests"
        elif "test" in dirs:
            info["test_dir"] = "test"
        elif "__tests__" in dirs:
            info["test_dir"] = "__tests__"

        if "pytest.ini" in files or any(f.startswith("test_") for f in files):
            info["runner"] = "pytest"
        elif "package.json" in files:
            info["runner"] = "npm test"
        elif "Cargo.toml" in files:
            info["runner"] = "cargo test"
        elif "go.mod" in files:
            info["runner"] = "go test ./..."
        else:
            info["runner"] = "pytest"

        return info
