"""Get the file ids of output files from a list of tasks."""

import sys
import click
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def check_and_get_files(task):
    """
    Check that a task is COMPLETED and get files.
    Inputs:
    - api object
    - task id

    Returns:
    - if the task is succesful: a list of output file ids
    """
    files = []
    if task.status == "COMPLETED":
        # get list of files in output folder
        for out_key in task.outputs.keys():
            if type(task.outputs[out_key]) is list:
                for file in task.outputs[out_key]:
                    if type(file) is list:
                        for f in file:
                            if f is not None:
                                files.append(f)
                    else:
                        if file is not None:
                            files.append(file)
            else:
                if task.outputs[out_key] is not None:
                    files.append(task.outputs[out_key])

    elif task.status == "DRAFT":
        print(f"{task.name} is a draft task and has not run yet, skipping", file=sys.stderr)
    elif task.status == "RUNNING":
        print(f"{task.name} is currently running, skipping", file=sys.stderr)
    elif task.status == "FAILED":
        print(f"{task.name} has failed, skipping", file=sys.stderr)
    else:
        print(f"{task.name} is in an unknown state: {task.status}", file=sys.stderr)
        print("Please check the task status and try again, skipping", file=sys.stderr)

    return files


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--task_file", help="File with task ids")
@click.option("--task_id", help="Task id")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def get_task_files(task_file, task_id, profile, debug):
    """
    Take a task or a list of tasks and find all output files.
    """
    # read config file
    api = hf.parse_config(profile)

    # get all of the tasks either from --task_id or reading the --task_file file
    all_tasks = []
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id", file=sys.stderr)
        exit(1)
    elif task_id:
        all_tasks.append(api.tasks.get(id=task_id))
    elif task_file:
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                all_tasks.append(api.tasks.get(id=task_id))

    print(f"file_name\tfile_id")
    for task in all_tasks:
        files_to_display = []
        files_to_display = check_and_get_files(task)

        if debug:
            print(f"Current task id: {task.id}  {task.name}")

        # loop through files and add any secondary files, and check that both files exist
        for file in files_to_display:
            try:
                file_obj = api.files.get(id=file)
            except NotFound as e:
                print(f"Can't find {file}, file doesn't exist", file=sys.stderr)

            if file.secondary_files is not None:
                for secondary in file.secondary_files:
                    try:
                        file_obj = api.files.get(id=secondary)
                    except NotFound as e:
                        print(f"Can't find {file.name}, file doesn't exist", file=sys.stderr)
                    # check if secondary already in list
                    if secondary not in files_to_display:
                        files_to_display.append(secondary)

        if len(files_to_display) > 0:
            # format output
            for file in files_to_display:
                print(f"{file.name}\t{file.id}")
        else:
            print("No files found in input task(s)")


if __name__ == "__main__":
    get_task_files()
