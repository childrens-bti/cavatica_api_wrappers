"""Script to automatically track and report active tasks."""

import subprocess
import json
import click
from pathlib import Path
from datetime import datetime, timedelta
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def notify(title, text):
    """
    Send macos notification with title and text
    """
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{text}" with title "{title}"',
        ]
    )


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def report_tasks(profile):
    """Report tasks that have finished"""
    # read config file
    api = hf.parse_config(profile)

    completed_tasks = []
    failed_tasks = []
    projects = []

    last_hour = (datetime.now().astimezone() - timedelta(hours=1)).isoformat(
        timespec="seconds"
    )
    last_day = (datetime.now().astimezone() - timedelta(hours=24)).isoformat(
        timespec="seconds"
    )

    # if now is during business hours (9am-6pm)
    # report on tasks from the last hour
    # otherwise report on tasks from the last 24 hours
    if 9 <= datetime.now().hour < 18:
        end_time = last_hour
    else:
        end_time = last_day

    all_tasks = hf.query_tasks(api, ended_from=end_time)
    for task in all_tasks:
        try:
            task = api.tasks.get(task.id)
        except Exception as e:
            print(f"Error getting task {task.id}: {e}")
            continue
        if task.status.upper() == "COMPLETED":
            completed_tasks.append(task.id)
        elif task.status.upper() == "FAILED":
            failed_tasks.append(task.id)
        if task.project not in projects:
            projects.append(task.project)

    title = "Cavatica Task Monitoring"
    short_message = f"completed: {len(completed_tasks)} tasks, failed: {len(failed_tasks)} tasks in {len(projects)} projects"
    print(f"{title}: {short_message}")

    notify(title, short_message)

    # write JSON report file in home
    home = Path.home()
    report_path = home / "task_report.json"
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "completed_task_count": len(completed_tasks),
        "failed_task_count": len(failed_tasks),
        "projects": projects,
        "completed_task_ids": completed_tasks,
        "failed_task_ids": failed_tasks,
    }
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)


if __name__ == "__main__":
    report_tasks()
