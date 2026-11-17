"""Credenciales efímeras desde la sesión gcloud del operador para comandos puntuales."""

from __future__ import annotations

import subprocess
import os

from google.oauth2.credentials import Credentials


def credentials_from_gcloud(account: str | None = None) -> Credentials:
    """Use gcloud's active account without exposing or persisting its access token."""
    command = ["gcloud", "auth", "print-access-token"]
    account_option = ""
    if account:
        command.extend(["--account", account])
        account_option = " --account '" + account.replace("'", "''") + "'"
    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; $token=(& gcloud auth print-access-token" + account_option + "); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; [Console]::Out.Write($token)",
        ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("gcloud no devolvió un token de acceso.")
    return Credentials(token=token)
