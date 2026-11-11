"""PyInstaller entry point (absolute import - a package __main__ cannot be frozen directly)."""

from ghost_ai.app import main

raise SystemExit(main())
