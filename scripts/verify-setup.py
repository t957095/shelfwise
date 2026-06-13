#!/usr/bin/env python3
"""
ShelfWise Setup Verification Script
Run this before recording your demo video to ensure everything is ready.
"""

import sys
import os
import subprocess
from pathlib import Path


def check(name, condition, fix_hint=""):
    status = "✓" if condition else "✗"
    color = "\033[92m" if condition else "\033[91m"
    reset = "\033[0m"
    print(f"  {color}{status}{reset} {name}")
    if not condition and fix_hint:
        print(f"      → {fix_hint}")
    return condition


def main():
    print("=" * 60)
    print("ShelfWise Setup Verification")
    print("=" * 60)

    all_ok = True
    project_root = Path(__file__).parent.parent.resolve()
    backend_dir = project_root / "backend"

    # Python version
    print("\n Python Environment")
    py_version = sys.version_info
    all_ok &= check(
        f"Python {py_version.major}.{py_version.minor}.{py_version.micro}",
        py_version >= (3, 12),
        "Upgrade to Python 3.12 or higher"
    )

    # Required packages
    print("\n Dependencies")
    required = ["fastapi", "uvicorn", "httpx", "bs4", "pydantic"]
    for pkg in required:
        try:
            __import__(pkg)
            all_ok &= check(f"{pkg} installed", True)
        except ImportError:
            all_ok &= check(f"{pkg} installed", False, f"pip install {pkg}")

    # Backend modules importable
    print("\n Backend Modules")
    sys.path.insert(0, str(project_root))
    modules = ["backend.main", "backend.scraper", "backend.foundry_agent", "backend.database", "backend.models"]
    for mod in modules:
        try:
            __import__(mod)
            all_ok &= check(f"{mod} imports", True)
        except Exception as e:
            all_ok &= check(f"{mod} imports", False, str(e))

    # .env file
    print("\n Configuration")
    env_file = backend_dir / ".env"
    env_example = backend_dir / ".env.example"
    has_env = check(".env file exists", env_file.exists(), f"Copy {env_example} to {env_file} and fill in values")
    all_ok &= has_env

    if env_file.exists():
        env_content = env_file.read_text()
        has_foundry = "FOUNDRY_ENDPOINT" in env_content and "FOUNDRY_API_KEY" in env_content
        check("Foundry IQ configured", has_foundry, "Optional: Add FOUNDRY_ENDPOINT and FOUNDRY_API_KEY for LLM enrichment")
    else:
        print("  ! Foundry IQ: Optional - app works without API keys using local reasoning engine")

    # Frontend files
    print("\n Frontend Files")
    frontend_dir = project_root / "frontend"
    for fname in ["index.html", "styles.css", "app.js"]:
        fpath = frontend_dir / fname
        all_ok &= check(f"frontend/{fname} exists", fpath.exists())

    # Database
    print("\n Database")
    db_file = backend_dir / "shelfwise.db"
    if db_file.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            conn.close()
            all_ok &= check("Database initialized", "products" in tables and "jobs" in tables)
        except Exception as e:
            all_ok &= check("Database readable", False, str(e))
    else:
        all_ok &= check("Database exists", False, "Start the server once to initialize the database")

    # Architecture diagram
    print("\n Documentation")
    arch_file = project_root / "architecture.html"
    all_ok &= check("architecture.html exists", arch_file.exists())
    readme_file = project_root / "README.md"
    all_ok &= check("README.md exists", readme_file.exists())

    # Docker
    print("\n Docker")
    dockerfile = project_root / "Dockerfile"
    docker_compose = project_root / "docker-compose.yml"
    all_ok &= check("Dockerfile exists", dockerfile.exists())
    all_ok &= check("docker-compose.yml exists", docker_compose.exists())

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All checks passed. You are ready to record your demo!")
        print(f"  Start server: cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000")
        print(f"  Open: http://localhost:8000/app/")
    else:
        print("✗ Some checks failed. Fix the issues above before recording.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
