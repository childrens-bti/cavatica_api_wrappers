"""Run a list of draft tasks getting id from file."""

import click
import configparser
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--task_file", help="File with task ids")
@click.option("--task_id", help="Task id")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def launch_task(task_file, task_id, profile, run):
    """
    Launch a single task using the task id or
    launch multiple tasks getting the task ids from input file.
    Task file is a file with task ids one per line.
    This will only launch draft tasks and cannot create tasks.
    """
    # read config file
    api = hf.parse_config(profile)
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id")
        exit(1)
    elif task_id:
        print(f"Current task id: {task_id}")
        task = api.tasks.get(id=task_id)
        print(f"Current status: {task.status}")
        if run:
            task.run()
            print(f"Updated status: {task.status}")
            print("Task successfully launched")
        else:
            print("Task was not launched")
    elif task_file:
        print(f"Launching tasks from file: {task_file}")
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                print(f"Current task id: {task_id}")
                task = api.tasks.get(id=task_id)
                print(f"Current status: {task.status}")
                if run:
                    try:
                        task.run()
                        print(f"Updated status: {task.status}")
                        print("Task successfully launched")
                    except Exception as e:
                        print(f"An error occurred launching this task: {e}")
                else:
                    print("Task was not launched")


if __name__ == "__main__":
    launch_task()
