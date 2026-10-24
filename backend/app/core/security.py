import re
from pathlib import Path
from typing import Optional

class SecurityManager:
    """
    Enforces security boundaries, path traversal prevention,
    credential sanitization, and prompt injection defense.
    """
    
    @staticmethod
    def sanitize_untrusted_content(content: str, label: str = "REPOSITORY_CONTENT") -> str:
        """
        Wraps untrusted repository content with boundary tags to protect against prompt injection.
        """
        escaped = content.replace("<UNTRUSTED_INPUT>", "&lt;UNTRUSTED_INPUT&gt;")
        return f"\n<{label}>\n{escaped}\n</{label}>\n"

    @staticmethod
    def validate_safe_path(base_dir: Path, target_path: str) -> Path:
        """
        Validates that target_path resides strictly within base_dir.
        Throws PermissionError on path traversal attempt.
        """
        resolved_base = base_dir.resolve()
        resolved_target = (resolved_base / target_path).resolve()
        
        # Check if resolved_target starts with resolved_base
        try:
            resolved_target.relative_to(resolved_base)
        except ValueError:
            raise PermissionError(f"Security Alert: Path traversal detected! '{target_path}' is outside repository root.")
            
        return resolved_target

    @staticmethod
    def mask_credentials(text: str) -> str:
        """
        Redacts API keys, tokens, and secrets from logs and event payloads.
        """
        patterns = [
            (r'(ghp_[a-zA-Z0-9]{36})', 'ghp_***REDACTED***'),
            (r'(github_pat_[a-zA-Z0-9_]{82})', 'github_pat_***REDACTED***'),
            (r'(sk-[a-zA-Z0-9]{20,})', 'sk-***REDACTED***'),
            (r'(AIza[0-9A-Za-z-_]{35})', 'AIza***REDACTED***'),
            (r'(Bearer\s+[a-zA-Z0-9\.\-_]+)', 'Bearer ***REDACTED***'),
            (r'(password|secret|key|token)["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'\1: ***REDACTED***'),
        ]
        sanitized = text
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized
