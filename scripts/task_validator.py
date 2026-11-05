"""Validate CAVATICA task names against manifest bioassay IDs."""

from collections import Counter, defaultdict
import csv
from io import StringIO
import re

import click
from helper_functions import helper_functions as hf
from helper_functions.manifest_io import load_input

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
BAID_RE = re.compile(r"(?<![A-Za-z0-9])(BA_[A-Za-z0-9]{8})(?![A-Za-z0-9])")


def runtime_failure(exc):
    """Report an error that prevented validation from completing."""
    message = exc.format_message() if isinstance(exc, click.ClickException) else str(exc)
    click.echo(f"ERROR: {message}")
    click.echo("Validation failed.")
    raise click.exceptions.Exit(2) from exc


class ValidatorCommand(click.Command):
    """Give usage and runtime errors a consistent automation result."""

    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, args)
        except click.ClickException as exc:
            runtime_failure(exc)

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except click.exceptions.Exit:
            raise
        except Exception as exc:
            runtime_failure(exc)


def read_baid_rows(content, column_names, source, extract=False):
    """Read one BAID set per input row, preserving repeated options rows."""
    with StringIO(content, newline="") as handle:
        header = handle.readline()
        handle.seek(0)
        reader = csv.DictReader(
            handle, delimiter="\t" if "\t" in header else ",", strict=True
        )
        columns = [
            column for column in (reader.fieldnames or [])
            if column.strip().casefold() in column_names
        ]
        if len(columns) != 1:
            expected = " or ".join(sorted(column_names))
            raise click.ClickException(
                f"{source} must contain exactly one {expected} column"
            )
        baid_rows = []
        errors = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                errors.append(f"{source} line {reader.line_num}: wrong number of columns")
                continue
            if not any(value.strip() for value in row.values()):
                continue
            baid = row[columns[0]].strip()
            if extract:
                matches = frozenset(BAID_RE.findall(baid))
                if not matches:
                    errors.append(
                        f"{source} line {reader.line_num}: "
                        f"output_basename contains no BAID: {baid!r}"
                    )
                else:
                    baid_rows.append(matches)
            elif not BAID_RE.fullmatch(baid):
                errors.append(f"{source} line {reader.line_num}: invalid BAID {baid!r}")
            else:
                baid_rows.append(frozenset({baid}))
        if errors:
            raise click.ClickException("\n".join(errors))
        if not baid_rows:
            raise click.ClickException(f"{source} contains no BAIDs")
    return baid_rows


def read_manifest_baids(manifest, demo=False):
    """Read the cohort BAIDs from a local or GitHub manifest."""
    rows = read_baid_rows(
        load_input(manifest, demo=demo), {"bioassay_id", "baid"}, "Manifest"
    )
    return set().union(*rows)


def read_options_rows(options_file, demo=False):
    """Count complete BAID sets extracted from each options output basename."""
    return Counter(read_baid_rows(
        load_input(options_file, demo=demo, option="--options_file"),
        {"output_basename"}, "Options file", extract=True,
    ))


@click.command(cls=ValidatorCommand, context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
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
    help="Full cohort main-branch manifest URL with a Bioassay_ID or BAID column; local CSV/TSV files require --demo",
)
@click.option(
    "--options_file",
    required=True,
    help="Workflow options main-branch URL with BAIDs in output_basename; local CSV/TSV files require --demo",
)
@click.option(
    "--demo",
    is_flag=True,
    help="Allow local manifest/options files and tasks with any status",
)
def task_validator(profile, task_file, manifest, options_file, demo):
    """Compare cohort manifest, workflow options, and task-name BAIDs.

    GitHub files must be on main. Require DRAFT tasks unless --demo is given.
    Repeated manifest BAIDs are expected for multiple input files. Report
    discrepancies and exit with status 1 when any are found, or status 2
    when an input, credential, download, or API error prevents validation.
    """
    try:
        manifest_baids = read_manifest_baids(manifest, demo=demo)
        expected_rows = read_options_rows(options_file, demo=demo)
        expected_baids = set().union(*expected_rows)
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

    discrepancies = [
        f"Options BAID not in manifest: {baid}"
        for baid in sorted(expected_baids - manifest_baids)
    ]
    runtime_errors = []
    row_tasks = defaultdict(list)
    task_rows = Counter()
    task_baids = set()
    for task_id, count in task_counts.items():
        if count > 1:
            discrepancies.append(f"Duplicate task ID: {task_id} ({count} entries)")
        try:
            task = api.tasks.get(id=task_id)
            name = task.name
            if not isinstance(name, str):
                raise ValueError("task name is not a string")
            status = task.status if not demo else None
        except Exception as exc:
            runtime_errors.append(f"Unable to retrieve task {task_id}: {exc}")
            continue
        if not demo and status != "DRAFT":
            discrepancies.append(
                f"Task is not DRAFT (status: {status}): {task_id}\t{name}"
            )
        baids = frozenset(BAID_RE.findall(name))
        if not baids:
            discrepancies.append(f"Task name contains no BAID: {task_id}\t{name}")
        else:
            task_rows[baids] += 1
            row_tasks[baids].append((task_id, name))
            task_baids.update(baids)
        for baid in sorted(baids):
            if baid not in expected_baids:
                discrepancies.append(
                    f"Unexpected BAID {baid} (not in options file): {task_id}\t{name}"
                )
            if baid not in manifest_baids:
                discrepancies.append(
                    f"Task BAID not in manifest {baid}: {task_id}\t{name}"
                )

    for baid in sorted(expected_baids - task_baids):
        discrepancies.append(f"Missing BAID (options sample has no retrieved task): {baid}")
    for row, count in sorted((expected_rows - task_rows).items(), key=lambda item: sorted(item[0])):
        label = "_".join(sorted(row))
        discrepancies.append(
            f"No task for options row: {label} "
            f"(missing {count} of {expected_rows[row]} tasks)"
        )
    for row, count in sorted((task_rows - expected_rows).items(), key=lambda item: sorted(item[0])):
        label = "_".join(sorted(row))
        details = "; ".join(f"{task_id}\t{name}" for task_id, name in row_tasks[row])
        discrepancies.append(
            f"Task does not match an options row (or is an extra task for one): "
            f"{label} ({count} extra tasks): {details}"
        )

    matched = len(expected_baids & task_baids)
    click.echo(
        f"Checked {len(task_counts)} unique task IDs against "
        f"{len(expected_baids)} unique options BAIDs and "
        f"{len(manifest_baids)} unique manifest BAIDs; {matched} BAIDs matched."
    )
    click.echo(
        f"Matched {sum((expected_rows & task_rows).values())} "
        f"of {sum(expected_rows.values())} options rows."
    )
    if discrepancies or runtime_errors:
        for discrepancy in discrepancies:
            click.echo(discrepancy)
        for error in runtime_errors:
            click.echo(error)
        click.echo(
            f"Found {len(discrepancies)} discrepancies and "
            f"{len(runtime_errors)} runtime errors."
        )
        click.echo("Validation failed.")
        raise click.exceptions.Exit(2 if runtime_errors else 1)
    for row, count in sorted(expected_rows.items(), key=lambda item: sorted(item[0])):
        if count > 1:
            click.echo(
                f"WARNING: Duplicate options row BAID set: {'_'.join(sorted(row))} "
                f"({count} rows, each matched by a separate task)."
            )
    if expected_baids < manifest_baids:
        click.echo(
            f"WARNING: Options file contains {len(expected_baids)} of "
            f"{len(manifest_baids)} manifest samples; "
            f"{len(manifest_baids - expected_baids)} manifest samples "
            "are not included in this run."
        )
    click.echo("Validation passed.")


if __name__ == "__main__":
    task_validator()
