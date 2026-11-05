"""Shared local/GitHub input loading and CSV/TSV manifest parsing."""

import csv
from io import StringIO
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import click
import requests


def has_dot_path_segment(path):
    """Return whether a URL path contains a literal or encoded dot segment.

    Requests normalizes literal ``.`` and ``..`` segments before sending a
    request. Decode repeatedly so encoded (including double-encoded) dot
    segments cannot change the path after the branch check.
    """
    for segment in path.split("/"):
        decoded = segment
        while True:
            unquoted = unquote(decoded)
            if unquoted == decoded:
                break
            decoded = unquoted
        if any(part in {".", ".."} for part in decoded.split("/")):
            return True
    return False


def load_input(path_or_url, demo=False, option="--manifest"):
    """Load a GitHub main-branch input, allowing local files in demo mode."""
    parsed = urlparse(path_or_url)
    if demo and not parsed.scheme and not parsed.netloc:
        return Path(path_or_url).read_text(encoding="utf-8-sig")
    if parsed.scheme != "https" or parsed.netloc != "raw.githubusercontent.com":
        raise click.ClickException(
            f"{option} must be an HTTPS raw.githubusercontent.com URL; "
            "use --demo to allow a local CSV/TSV file"
        )
    if has_dot_path_segment(parsed.path):
        raise click.ClickException(f"{option} must not contain dot path segments")
    path_parts = parsed.path.strip("/").split("/")
    is_main = len(path_parts) >= 4 and path_parts[2] == "main"
    is_main_ref = len(path_parts) >= 6 and path_parts[2:5] == ["refs", "heads", "main"]
    if not is_main and not is_main_ref:
        raise click.ClickException(f"{option} must point to a file on the GitHub main branch")
    if parsed.query or parsed.fragment:
        raise click.ClickException(
            "Use a token-free GitHub raw URL; set GITHUB_TOKEN or GH_TOKEN "
            "for private repositories"
        )
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    try:
        response = requests.get(path_or_url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        label = "options file" if option == "--options_file" else "manifest"
        raise click.ClickException(
            f"Could not download {label} {path_or_url}: {exc}"
        ) from exc
    return response.content.decode("utf-8-sig")


def read_manifest(content, source):
    """Read a CSV or TSV manifest without loading it into a data-frame."""
    try:
        lines = content.splitlines()
        header = lines[0] if lines else ""
        delimiter = "\t" if "\t" in header else ","
        reader = csv.DictReader(StringIO(content), delimiter=delimiter)
        if not reader.fieldnames:
            raise click.ClickException("Manifest has no header")
        rows = [
            {key.strip(): (value or "").strip() for key, value in row.items()}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
    except csv.Error as exc:
        raise click.ClickException(f"Could not parse manifest {source}: {exc}") from exc
    if not rows:
        raise click.ClickException(f"Manifest contains no data rows: {source}")
    return rows

