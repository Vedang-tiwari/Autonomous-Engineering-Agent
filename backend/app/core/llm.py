import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseLLM(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response text from LLM given prompt and system instructions."""
        pass

    async def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Generate response and parse as JSON."""
        system_with_json = system_prompt + "\nIMPORTANT: Return ONLY a valid JSON object. Do not wrap with markdown backticks or commentary."
        raw = await self.generate(prompt, system_prompt=system_with_json)
        raw_clean = raw.strip()
        if raw_clean.startswith("```json"):
            raw_clean = raw_clean[7:]
        elif raw_clean.startswith("```"):
            raw_clean = raw_clean[3:]
        if raw_clean.endswith("```"):
            raw_clean = raw_clean[:-3]
        raw_clean = raw_clean.strip()
        try:
            return json.loads(raw_clean)
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}. Raw: {raw_clean[:200]}")
            # Try finding first { and last }
            start = raw_clean.find("{")
            end = raw_clean.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw_clean[start:end+1])
            raise e


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.url = "https://api.openai.com/v1/chat/completions"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class GeminiLLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Directive:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these directives."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class AnthropicLLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        self.api_key = api_key
        self.model = model
        self.url = "https://api.anthropic.com/v1/messages"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]


class MockLLM(BaseLLM):
    """
    Intelligent simulated agent engine that generates realistic plans,
    diagnoses, patches, and reviews for autonomous agent execution and testing.
    """
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        prompt_lower = prompt.lower()
        if "plan" in prompt_lower or "decompose" in prompt_lower:
            return json.dumps({
                "plan_overview": "Structured execution plan for autonomous repository task.",
                "steps": [
                    {"step_number": 1, "title": "Inspect Repository Structure", "description": "Detect tech stack, dependency definitions, test runners, and architecture."},
                    {"step_number": 2, "title": "Analyze Task and Identify Relevant Code", "description": "Locate files, functions, and unit tests associated with the objective."},
                    {"step_number": 3, "title": "Execute Existing Test Suite", "description": "Run sandbox tests to reproduce failures or establish baseline."},
                    {"step_number": 4, "title": "Formulate Diagnosis & Apply Code Patch", "description": "Modify implementation and add regression tests to prevent recurrences."},
                    {"step_number": 5, "title": "Verify Changes in Sandbox", "description": "Re-run test suite, linter, and type checks to confirm fix validity."},
                    {"step_number": 6, "title": "Automated Code Review", "description": "Review git diff for correctness, performance, and security regressions."},
                    {"step_number": 7, "title": "Git Operations & Pull Request", "description": "Create feature branch, commit validated modifications, and prepare PR."}
                ]
            })

        if "diagnose" in prompt_lower or "root cause" in prompt_lower or "fix" in prompt_lower:
            return json.dumps({
                "root_cause": "Identified defect or missing requirement in core implementation logic.",
                "affected_files": ["src/main.py", "tests/test_main.py"],
                "solution_strategy": "Implement corrective logic, validate input boundaries, and register regression assertions.",
                "proposed_modifications": [
                    {
                        "file_path": "src/main.py",
                        "description": "Fix bug and enforce validation",
                        "action": "modify"
                    }
                ]
            })

        if "review" in prompt_lower or "diff" in prompt_lower:
            return json.dumps({
                "decision": "APPROVED",
                "summary": "The implemented modifications cleanly resolve the stated task requirements. Regression tests confirm zero breaking changes.",
                "quality_score": 95,
                "issues": [],
                "security_concerns": [],
                "regression_risk": "low",
                "recommendation": "Ready to merge via Pull Request."
            })

        return json.dumps({
            "status": "success",
            "message": "Autonomous engineering task completed successfully.",
            "details": prompt[:100]
        })


def get_llm_client() -> BaseLLM:
    """Factory to retrieve configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai" and (settings.OPENAI_API_KEY or settings.LLM_API_KEY):
        key = settings.OPENAI_API_KEY or settings.LLM_API_KEY
        return OpenAILLM(api_key=key, model=settings.LLM_MODEL or "gpt-4o")

    if provider == "gemini" and (settings.GEMINI_API_KEY or settings.LLM_API_KEY):
        key = settings.GEMINI_API_KEY or settings.LLM_API_KEY
        return GeminiLLM(api_key=key, model=settings.LLM_MODEL or "gemini-1.5-pro")

    if provider == "anthropic" and (settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY):
        key = settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY
        return AnthropicLLM(api_key=key, model=settings.LLM_MODEL or "claude-3-5-sonnet-20240620")

    return MockLLM()
