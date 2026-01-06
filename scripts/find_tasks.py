"""Simple script to tasks in a project."""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--status",
    help="comma-separated list of task statuses to find",
    default="COMPLETED",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_tasks(project, profile, status):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    # get all tasks in project
    all_tasks = hf.get_all_tasks(api, project)

    stati = [s.strip().upper() for s in status.split(",")]


    print("Task Name\tTask Id\tStart Time\tEnd Time\tTask Status")


    for task in all_tasks:
       if task.status.upper() in stati:
          print(f"{task.name}\t{task.id}\t{task.start_time}\t{task.end_time}\t{task.status}")

            #print(dir(task))


if __name__ == "__main__":
    find_tasks()
