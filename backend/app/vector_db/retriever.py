import os
import math
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

class CodeChunk:
    def __init__(self, file_path: str, start_line: int, end_line: int, content: str, symbols: List[str]):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.symbols = symbols

class CodeRetriever:
    """
    Repository Intelligence and Hybrid Retrieval engine.
    Parses code files, segments into semantic chunks, and performs
    token-frequency + symbol-aware hybrid retrieval for large codebases.
    """

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir.resolve()
        self.chunks: List[CodeChunk] = []
        self._indexed = False

    def index_repository(self):
        """Indexes source files in repository into code chunks."""
        self.chunks = []
        valid_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".json", ".yaml", ".yml", ".md"}

        for root, dirs, files in os.walk(self.repo_dir):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".next"}]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext not in valid_exts:
                    continue

                full_path = Path(root) / file
                rel_path = full_path.relative_to(self.repo_dir).as_posix()

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                if not lines:
                    continue

                # Segment into chunks of ~50-80 lines with overlap
                chunk_size = 60
                overlap = 15
                i = 0
                while i < len(lines):
                    chunk_lines = lines[i:i + chunk_size]
                    chunk_text = "".join(chunk_lines)

                    # Extract symbols (functions, classes, defs)
                    symbols = re.findall(r'(?:def|class|function|const|let|var|type|interface)\s+([A-Za-z0-9_]+)', chunk_text)

                    self.chunks.append(CodeChunk(
                        file_path=rel_path,
                        start_line=i + 1,
                        end_line=min(i + chunk_size, len(lines)),
                        content=chunk_text,
                        symbols=symbols
                    ))

                    if i + chunk_size >= len(lines):
                        break
                    i += (chunk_size - overlap)

        self._indexed = True

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves top_k most relevant code chunks for a given query
        using hybrid symbol matching + BM25-like token overlap.
        """
        if not self._indexed:
            self.index_repository()

        if not self.chunks:
            return []

        query_tokens = set(re.findall(r'[A-Za-z0-9_]+', query.lower()))
        scores = []

        for idx, chunk in enumerate(self.chunks):
            score = 0.0
            content_lower = chunk.content.lower()
            file_lower = chunk.file_path.lower()

            # 1. Exact phrase / token matches
            for token in query_tokens:
                if len(token) < 3:
                    continue
                # Higher weight if token in file path
                if token in file_lower:
                    score += 5.0
                # Higher weight if token in symbols
                for sym in chunk.symbols:
                    if token in sym.lower():
                        score += 8.0
                # Token count in content
                cnt = content_lower.count(token)
                if cnt > 0:
                    score += min(cnt * 1.5, 10.0)

            # Boost test files if query mentions tests or bugs
            if any(k in query.lower() for k in ["test", "fail", "assert"]) and "test" in file_lower:
                score += 3.0

            scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        top_indices = [idx for score, idx in scores[:top_k] if score > 0]

        results = []
        for idx in top_indices:
            c = self.chunks[idx]
            results.append({
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content,
                "symbols": c.symbols
            })

        return results
