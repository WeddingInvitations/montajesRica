"""Compatibilidad: concede el rol admin a una cuenta Google ya registrada en Firebase Auth."""

from __future__ import annotations

import sys

from scripts.set_user_role import main as set_user_role_main


if __name__ == "__main__":
    sys.argv[1:1] = ["--role", "admin"]
    raise SystemExit(set_user_role_main())
