"""Run a list of draft tasks getting id from file."""

import click
import time
from collections import deque
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
    help="Limit queued and running tasks from the input list; -1 means unlimited",
    default=50,
    type=int,
    show_default=True,
)
@click.option(
    "--wait",
    help="Time in minutes to wait between checking task status",
    default=60,
    type=click.IntRange(min=0),
    show_default=True,
)
@click.option(
    "--max_checks",
    help="Maximum status checks per active task before it must finish",
    default=12,
    type=click.IntRange(min=1),
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

    Technically, this isn't correct. An account can only launch
    80 instances at a time. Not tasks. Most of our workflows are
    configured to only launch 2 instances at a time.
    For now, this is a good enough approximation.
    """
    if limit != -1 and limit < 1:
        raise click.BadParameter("must be positive or -1", param_hint="--limit")

    # figure out which tasks to run
    all_tasks = []
    if task_file and task_id:
        raise click.UsageError("Please provide either a task file or a task id")
    elif task_id:
        print(f"Current task id: {task_id}")
        all_tasks = [task_id]
    elif task_file:
        print(f"Launching tasks from file: {task_file}")
        with open(task_file, "r") as f:
            all_tasks = [line.strip() for line in f if line.strip()]
    else:
        raise click.UsageError("Please provide either a task file or a task id")

    api = hf.parse_config(profile)
    pending_tasks = deque()
    running_tasks = {}
    if limit == -1:
        print("Running all input tasks without a concurrency limit")
    else:
        print(f"Running up to {limit} tasks at once")

    with open(f"{output_basename}_completed.txt", "a+") as comp_f, open(
        f"{output_basename}_failed.txt", "a+"
    ) as fail_f:
        comp_f.seek(0)
        fail_f.seek(0)
        completed_ids = {line.strip() for line in comp_f if line.strip()}
        failed_ids = {line.strip() for line in fail_f if line.strip()}

        def record_result(task_id, status):
            if status == "COMPLETED":
                output = comp_f
                recorded_ids = completed_ids
            elif status in ("FAILED", "ABORTED"):
                output = fail_f
                recorded_ids = failed_ids
            else:
                return False
            if task_id not in recorded_ids:
                output.write(f"{task_id}\n")
                output.flush()
                recorded_ids.add(task_id)
            return True

        # Inspect every unique input ID before launching anything so existing
        # queued/running tasks later in the file also count against the limit.
        for task_id in dict.fromkeys(all_tasks):
            task = api.tasks.get(id=task_id)
            if task.status == "DRAFT":
                pending_tasks.append(task_id)
            elif task.status in ("RUNNING", "QUEUED"):
                running_tasks[task_id] = 0
            elif not record_result(task_id, task.status):
                print(f"Skipping task {task_id}, status: {task.status}")

        while pending_tasks or running_tasks:
            # Refill available slots before waiting for the next status check.
            while pending_tasks and (limit == -1 or len(running_tasks) < limit):
                task_id = pending_tasks.popleft()
                task = api.tasks.get(id=task_id)
                if task.status == "DRAFT":
                    print(f"Launching task {task_id}")
                    try:
                        task.run()
                    except Exception as e:
                        print(f"An error occurred launching task {task_id}: {e}")
                        record_result(task_id, "FAILED")
                        continue
                    if task.status not in ("RUNNING", "QUEUED", "COMPLETED", "FAILED", "ABORTED"):
                        print(f"Task {task_id} failed to start, status: {task.status}")
                        record_result(task_id, "FAILED")
                        continue
                if task.status in ("RUNNING", "QUEUED"):
                    running_tasks[task_id] = 0
                elif not record_result(task_id, task.status):
                    print(f"Skipping task {task_id}, status: {task.status}")

            if not running_tasks:
                break

            print(f"Waiting {wait} minutes before checking task status...")
            time.sleep(wait * 60)
            for task_id in list(running_tasks):
                task = api.tasks.get(id=task_id)
                if record_result(task_id, task.status):
                    del running_tasks[task_id]
                else:
                    running_tasks[task_id] += 1

            stalled_tasks = sorted(
                task_id for task_id, checks in running_tasks.items() if checks >= max_checks
            )
            if stalled_tasks:
                raise click.ClickException(
                    f"Maximum status checks per active task reached ({max_checks}). "
                    f"Tasks may be stalled; inspect these active tasks: {', '.join(stalled_tasks)}"
                )

    print("All tasks processed")


if __name__ == "__main__":
    launch_task()
