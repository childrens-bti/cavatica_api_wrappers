"""Get the file ids of output files from a list of tasks."""

import sys
import click
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def get_regular_files(api, all_tasks, debug=False):
    """
    Get the file ids of output files from a list of tasks.
    Inputs:
    - api object
    - list of task objects
    Returns:
    - list of file objects
    """
    files_to_display = []
    for task in all_tasks:
        initial_files = []
        initial_files = check_and_get_files(task)

        if debug:
            print(f"Current task id: {task.id}  {task.name}", file=sys.stderr)

        # loop through files and add any secondary files, and check that both files exist
        for file in initial_files:
            try:
                file_obj = api.files.get(id=file.id)
            except NotFound:
                print(f"Can't find {file}, file doesn't exist", file=sys.stderr)
                continue

            if file_obj.is_folder():
                sub_files = hf.get_all_files_folder(api, file_obj)
                for f in sub_files:
                    if f.parent:
                        parent = api.files.get(id=f.parent)
                        f.name = f"{parent.name}/{f.name}"
                        while parent.parent:
                            parent = api.files.get(id=parent.parent)
                            if parent.parent is not None:
                                f.name = f"{parent.name}/{f.name}"
                    if not f.is_folder():
                        files_to_display.append(f)
            else:
                files_to_display.append(file)

            for secondary in file.secondary_files or []:
                try:
                    secondary_obj = api.files.get(id=secondary.id)
                except NotFound:
                    print(
                        f"Can't find {secondary}, file doesn't exist",
                        file=sys.stderr,
                    )
                    continue
                # check if secondary already in list
                if secondary_obj not in files_to_display:
                    files_to_display.append(secondary_obj)

    return files_to_display


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
        print(
            f"{task.name} is a draft task and has not run yet, skipping",
            file=sys.stderr,
        )
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
@click.option(
    "--output_file",
    "-o",
    help="Output filename",
    required=True,
)
def get_task_files(task_file, task_id, profile, debug, output_file):
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

    files_to_display = get_regular_files(api, all_tasks, debug)

    with open(output_file, "w") as out_f:
        out_f.write("file_name\tfile_id\n")
        if len(files_to_display) > 0:
            # format output
            for file in files_to_display:
                out_f.write(f"{file.name}\t{file.id}\n")
        else:
            out_f.write("No files found in input task(s)\n")


if __name__ == "__main__":
    get_task_files()
