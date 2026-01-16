"""Run a list of draft tasks getting id from file."""

import click
import configparser
import time
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
@click.option(
    "--limit",
    help="Limit number of tasks to run at once, set to -1 to run all task (not recommended)",
    default=50,
    type=int,
    show_default=True,
)
@click.option(
    "--wait",
    help="Time in minutes to wait between checking task status",
    default=60,
    type=int,
    show_default=True,
)
@click.option(
    "--max_checks",
    help="Maximum number of status checks to perform",
    default=12,
    type=int,
    show_default=True,
)
@click.option(
    "--output_basename",
    help="Base name for output files",
    default="task_status",
    show_default=True,
)
def launch_task(task_file, task_id, profile, limit, wait, max_checks, output_basename):
    """
    Launch a single task using the task id or
    launch multiple tasks getting the task ids from input file.
    Task file is a file with task ids one per line.
    This will only launch draft tasks and cannot create tasks.
    """
    # read config file
    api = hf.parse_config(profile)

    # figure out which tasks to run
    all_tasks = []
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id")
        exit(1)
    elif task_id:
        print(f"Current task id: {task_id}")
        all_tasks = [task_id]
        task = api.tasks.get(id=task_id)
        print(f"Current status: {task.status}")
    elif task_file:
        print(f"Launching tasks from file: {task_file}")
        with open(task_file, "r") as f:
            all_tasks = [line.strip() for line in f]
    else:
        print("ERROR: Please provide either a task file or a task id")
        exit(1)

    # start running tasks and keeping track of completed and failed tasks
    run_tasks = True
    completed_tasks = []
    failed_tasks = []
    print(f"Running up to {limit} tasks at once")
    while run_tasks:
        # figure out how many tasks we're running this round
        running_tasks = 0
        if limit == -1:
            tasks_to_run = all_tasks
            # is this message correct?
            print("Launching all tasks, status must be monitored manually")
        else:
            # this makes tasks_to_run the next 'limit' (ie 50) tasks from all_tasks
            tasks_to_run = all_tasks[:limit]

        running_tasks = []
        failed_tasks = []
        completed_tasks = []

        # run tasks
        print(f"Launching a batch of {limit} tasks")
        for task_id in tasks_to_run:
            task = api.tasks.get(id=task_id)
            if task.status == "DRAFT" and len(running_tasks) < limit:
                try:
                    task.run()
                    running_tasks.append(task_id)
                except Exception as e:
                    print(f"An error occurred launching this task: {e}")
                    failed_tasks.append(task_id)

        # check if the tasks are still running
        checks = 0
        while running_tasks and checks < max_checks:
            checks += 1
            print(f"Waiting {wait} minutes before checking task status...")
            time.sleep(wait * 60)
            for task_id in running_tasks[:]:
                task = api.tasks.get(id=task_id)
                if task.status == "COMPLETED":
                    completed_tasks.append(task_id)
                    running_tasks.remove(task_id)
                elif task.status == "FAILED":
                    failed_tasks.append(task_id)
                    running_tasks.remove(task_id)

        # write tasks to files based on status
        with open(f"{output_basename}_completed.txt", "a") as comp_f:
            for task_id in completed_tasks:
                comp_f.write(f"{task_id}\n")
        with open(f"{output_basename}_failed.txt", "a") as fail_f:
            for task_id in failed_tasks:
                fail_f.write(f"{task_id}\n")

        if checks == max_checks:
            print("Maximum number of checks reached, tasks may be stalled. Consider cancelling.")
            exit(1)

        # remove these tasks and repeat
        all_tasks = all_tasks[limit:]
        if not all_tasks:
            run_tasks = False

    print("All tasks processed")


if __name__ == "__main__":
    launch_task()
