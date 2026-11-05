"""Validate CAVATICA task names against manifest bioassay IDs."""

from collections import Counter, defaultdict
import csv
from io import StringIO
import os
from pathlib import Path
import re
from urllib.parse import urlparse

import click
import requests
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
BAID_RE = re.compile(r"(?<![A-Za-z0-9])(BA_[A-Za-z0-9]{8})(?![A-Za-z0-9])")


def load_manifest(manifest):
    """Load a local manifest or a raw GitHub manifest, including private repos."""
    parsed = urlparse(manifest)
    if not parsed.scheme and not parsed.netloc:
        return Path(manifest).read_text(encoding="utf-8-sig")
    if parsed.scheme != "https" or parsed.netloc != "raw.githubusercontent.com":
        raise click.ClickException(
            "--manifest must be a local file or an HTTPS raw.githubusercontent.com URL"
        )
    if parsed.query or parsed.fragment:
        raise click.ClickException(
            "Use a token-free GitHub raw URL; set GITHUB_TOKEN or GH_TOKEN "
            "for private repositories"
        )
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    try:
        response = requests.get(manifest, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise click.ClickException(f"Could not download manifest {manifest}: {exc}") from exc
    return response.content.decode("utf-8-sig")


def read_manifest_baids(manifest):
    """Read unique BAIDs from the Bioassay_ID (or BAID) CSV/TSV column."""
    with StringIO(load_manifest(manifest), newline="") as handle:
        header = handle.readline()
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter="\t" if "\t" in header else ",")
        columns = [
            column
            for column in (reader.fieldnames or [])
            if column.strip().casefold() in {"bioassay_id", "baid"}
        ]
        if len(columns) != 1:
            raise click.ClickException(
                "Manifest must contain exactly one Bioassay_ID or BAID column"
            )
        baids = set()
        errors = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                errors.append(
                    f"Manifest line {reader.line_num}: wrong number of columns"
                )
                continue
            if not any(value.strip() for value in row.values()):
                continue
            baid = row[columns[0]].strip()
            if not BAID_RE.fullmatch(baid):
                errors.append(f"Manifest line {reader.line_num}: invalid BAID {baid!r}")
            else:
                baids.add(baid)
        if errors:
            raise click.ClickException("\n".join(errors))
        if not baids:
            raise click.ClickException("Manifest contains no BAIDs")
    return baids


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
@click.option(
    "--task_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="File with task IDs, one per line",
)
@click.option(
    "--manifest",
    required=True,
    help="Local CSV/TSV file or HTTPS raw.githubusercontent.com URL with a Bioassay_ID or BAID column",
)
def task_validator(profile, task_file, manifest):
    """Compare BAIDs in task names with unique manifest Bioassay_ID values.

    Repeated manifest BAIDs are expected for multiple input files. Report
    discrepancies and exit with status 1 when any are found.
    """
    try:
        expected_baids = read_manifest_baids(manifest)
        with open(task_file, encoding="utf-8-sig") as handle:
            task_counts = Counter(line.strip() for line in handle if line.strip())
    except (OSError, UnicodeError, csv.Error) as exc:
        raise click.ClickException(f"Unable to read input files: {exc}") from exc
    if not task_counts:
        raise click.ClickException("Task file contains no task IDs")
    try:
        api = hf.parse_config(profile)
    except Exception as exc:
        raise click.ClickException(
            f"Unable to load API credentials for profile {profile!r}: {exc}"
        ) from exc

    discrepancies = []
    baid_tasks = defaultdict(list)
    for task_id, count in task_counts.items():
        if count > 1:
            discrepancies.append(f"Duplicate task ID: {task_id} ({count} entries)")
        try:
            task = api.tasks.get(id=task_id)
            name = task.name
            if not isinstance(name, str):
                raise ValueError("task name is not a string")
        except Exception as exc:
            discrepancies.append(f"Unable to retrieve task {task_id}: {exc}")
            continue
        baids = set(BAID_RE.findall(name))
        if not baids:
            discrepancies.append(f"Task name contains no BAID: {task_id}\t{name}")
        for baid in sorted(baids):
            baid_tasks[baid].append((task_id, name))
            if baid not in expected_baids:
                discrepancies.append(f"Unexpected BAID {baid}: {task_id}\t{name}")

    for baid in sorted(expected_baids - baid_tasks.keys()):
        discrepancies.append(f"Missing BAID (no retrieved task matches): {baid}")
    for baid, tasks in sorted(baid_tasks.items()):
        if len(tasks) > 1:
            details = "; ".join(f"{task_id}\t{name}" for task_id, name in tasks)
            discrepancies.append(f"Multiple tasks for BAID {baid}: {details}")

    matched = len(expected_baids & baid_tasks.keys())
    click.echo(
        f"Checked {len(task_counts)} unique task IDs against "
        f"{len(expected_baids)} unique manifest BAIDs; {matched} BAIDs matched."
    )
    if discrepancies:
        for discrepancy in discrepancies:
            click.echo(discrepancy)
        click.echo(f"Validation failed: {len(discrepancies)} discrepancies.")
        raise click.exceptions.Exit(1)
    click.echo("Validation passed: all manifest BAIDs have exactly one matching task.")


if __name__ == "__main__":
    task_validator()
