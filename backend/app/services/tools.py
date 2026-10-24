import os
import re
import difflib
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.security import SecurityManager

class RepositoryTools:
    """
    Controlled toolset for agents to interact safely with a target repository.
    Enforces security boundary, path validation, and structured responses.
    """

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir.resolve()

    def read_file(self, relative_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        """Reads content from a file inside the repository with line range support."""
        try:
            safe_path = SecurityManager.validate_safe_path(self.repo_dir, relative_path)
            if not safe_path.exists() or not safe_path.is_file():
                return {"success": False, "error": f"File '{relative_path}' not found."}

            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s = (start_line - 1) if (start_line and start_line > 0) else 0
            e = end_line if (end_line and end_line <= total_lines) else total_lines

            selected_lines = lines[s:e]
            content = "".join(selected_lines)

            return {
                "success": True,
                "path": relative_path,
                "content": content,
                "total_lines": total_lines,
                "start_line": s + 1,
                "end_line": e
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """Creates or overwrites a file safely within repository root."""
        try:
            safe_path = SecurityManager.validate_safe_path(self.repo_dir, relative_path)
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            old_content = ""
            if safe_path.exists():
                with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                    old_content = f.read()

            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Generate unified diff
            diff = "".join(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}"
            ))

            return {
                "success": True,
                "path": relative_path,
                "action": "modify" if old_content else "create",
                "diff": diff,
                "lines_added": sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")),
                "lines_removed": sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_patch(self, relative_path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """Applies a targeted string replacement patch to a file."""
        try:
            safe_path = SecurityManager.validate_safe_path(self.repo_dir, relative_path)
            if not safe_path.exists():
                return {"success": False, "error": f"File '{relative_path}' not found."}

            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if old_str not in content:
                return {"success": False, "error": f"Target content not found in '{relative_path}'."}

            patched_content = content.replace(old_str, new_str, 1)

            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(patched_content)

            diff = "".join(difflib.unified_diff(
                content.splitlines(keepends=True),
                patched_content.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}"
            ))

            return {
                "success": True,
                "path": relative_path,
                "diff": diff
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_dir(self, relative_path: str = "") -> Dict[str, Any]:
        """Lists directory entries safely within repository root."""
        try:
            safe_path = SecurityManager.validate_safe_path(self.repo_dir, relative_path)
            if not safe_path.exists() or not safe_path.is_dir():
                return {"success": False, "error": f"Directory '{relative_path}' not found."}

            entries = []
            for item in safe_path.iterdir():
                # Skip .git and binary heavy directories
                if item.name in {".git", ".venv", "node_modules", "__pycache__"}:
                    continue
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else None
                })

            return {"success": True, "entries": sorted(entries, key=lambda x: (not x["is_dir"], x["name"]))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_code(self, query: str, regex: bool = False, file_extension: Optional[str] = None) -> Dict[str, Any]:
        """Searches repository files for exact or regex query matches."""
        results = []
        try:
            compiled_regex = re.compile(query, re.IGNORECASE) if regex else None
            query_lower = query.lower()

            for root, dirs, files in os.walk(self.repo_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}]

                for file in files:
                    if file_extension and not file.endswith(file_extension):
                        continue

                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(self.repo_dir).as_posix()

                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                match = compiled_regex.search(line) if compiled_regex else (query_lower in line.lower())
                                if match:
                                    results.append({
                                        "file": rel_path,
                                        "line_number": idx,
                                        "content": line.strip()
                                    })
                                    if len(results) >= 50:
                                        return {"success": True, "matches": results, "capped": True}
                    except Exception:
                        continue

            return {"success": True, "matches": results, "capped": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
