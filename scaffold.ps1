$paths = @(
  ".github/workflows",
  "backend/app/api",
  "backend/app/agents",
  "backend/app/core",
  "backend/app/db",
  "backend/app/vector_db",
  "backend/app/tasks",
  "backend/app/services",
  "backend/app/sandbox",
  "backend/app/schemas",
  "backend/tests",
  "frontend/src/app",
  "frontend/src/components",
  "frontend/src/hooks",
  "frontend/src/services",
  "sandbox-environment",
  "infrastructure"
)
foreach ($path in $paths) {
  New-Item -ItemType Directory -Force -Path $path
}

$files = @(
  ".github/workflows/ci.yml",
  "backend/app/__init__.py",
  "backend/app/main.py",
  "backend/app/api/__init__.py",
  "backend/app/agents/__init__.py",
  "backend/app/agents/planner.py",
  "backend/app/agents/repository.py",
  "backend/app/agents/coding.py",
  "backend/app/agents/testing.py",
  "backend/app/agents/review.py",
  "backend/app/agents/git.py",
  "backend/app/core/__init__.py",
  "backend/app/db/__init__.py",
  "backend/app/vector_db/__init__.py",
  "backend/app/tasks/__init__.py",
  "backend/app/services/__init__.py",
  "backend/app/sandbox/__init__.py",
  "backend/app/schemas/__init__.py",
  "backend/tests/__init__.py",
  "backend/requirements.txt",
  "backend/Dockerfile",
  "frontend/src/app/globals.css",
  "frontend/src/app/layout.tsx",
  "frontend/src/app/page.tsx",
  "frontend/package.json",
  "frontend/next.config.js",
  "frontend/Dockerfile",
  "sandbox-environment/Dockerfile",
  "sandbox-environment/entrypoint.sh",
  "infrastructure/docker-compose.yml",
  "README.md"
)
foreach ($file in $files) {
  New-Item -ItemType File -Force -Path $file
}
