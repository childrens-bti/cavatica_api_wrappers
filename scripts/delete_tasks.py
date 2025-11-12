import click
from sevenbridges.errors import SbgError, NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

ACTIVE_STATI = {"QUEUED", "RUNNING"}
DRAFT_STATI = {"DRAFT"}


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url"
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def delete_tasks(profile, project, run):
    """
    Find DRAFT and/or active (QUEUED/RUNNING) tasks and/or delete/abort them.:
      - delete DRAFT tasks
      - abort active tasks
    """
    # Auth
    api = hf.parse_config(profile)

    # Discover tasks
    all_tasks = hf.get_all_tasks(api, project)

    draft_tasks = []
    active_tasks = []
    for task in all_tasks:
        status = (task.status or "").upper()
        if status in DRAFT_STATI:
            draft_tasks.append(task)
        elif status in ACTIVE_STATI:
            active_tasks.append(task)

    click.echo(
        f"Found {len(draft_tasks)} DRAFT tasks and {len(active_tasks)} active tasks (QUEUED/RUNNING)."
    )

    # Preview
    if draft_tasks:
        click.echo("\n[DRAFT] Tasks to delete:")
        for t in draft_tasks:
            click.echo(f"{t.id}, {t.name}, {t.status}")
    if active_tasks:
        click.echo("\n[ACTIVE] Tasks to abort:")
        for t in active_tasks:
            click.echo(f"{t.id}, {t.name}, {t.status}")

    if not run:
        click.echo("\n[dry-run] No actions taken. Re-run with --run to apply.")
        click.echo("Done!")
        return

    # Delete drafts
    for t in draft_tasks:
        try:
            click.echo(f"[delete] DRAFT {t.id} — {t.name}")
            t.delete()
        except NotFound:
            click.echo(f"[skip] DRAFT {t.id} already deleted, skipping")
        except SbgError as e:
            click.echo(f"[error] Failed to delete DRAFT {t.id}: {e}")

    # Abort active
    for t in active_tasks:
        try:
            click.echo(f"[abort] {t.status} {t.id} — {t.name}")
            t.abort()
        except SbgError as e:
            click.echo(f"[error] Failed to abort {t.id}: {e}")

    click.echo("Done!")


if __name__ == "__main__":
    delete_tasks()
