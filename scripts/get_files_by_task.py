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
            print(f"Current task id: {task.id}  {task.name}")

        # loop through files and add any secondary files, and check that both files exist
        for file in initial_files:
            try:
                file_obj = api.files.get(id=file)
            except NotFound as e:
                print(f"Can't find {file}, file doesn't exist", file=sys.stderr)

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

            if file_obj.secondary_files is not None:
                for secondary in file.secondary_files:
                    try:
                        file_obj = api.files.get(id=secondary)
                    except NotFound as e:
                        print(
                            f"Can't find {file_obj.name}, file doesn't exist",
                            file=sys.stderr,
                        )
                    # check if secondary already in list
                    if secondary not in files_to_display:
                        files_to_display.append(secondary)

    return files_to_display


def get_scrna_files(api, all_tasks, debug=False):
    """
    Get the file ids of output files from a list of scRNA tasks.
    For scRNA tasks, the output file is just a folder.
    Go through that folder, look for the results folder,
    get all of the fiels in subfolders of the results folder.
    Inputs:
    - api object
    - list of task objects
    Returns:
    - list of file objects
    """
    limit = hf.LIMIT if hasattr(hf, "LIMIT") else 50
    display_files = []

    for task in all_tasks:
        if debug:
            print(f"Current task id: {task.id}  {task.name}")

        root_files = check_and_get_files(task)
        if len(root_files) > 1:
            raise ValueError("More than one output file found, task is not scrna.")

        try:
            file_obj = api.files.get(id=root_files[0])
        except NotFound:
            print(f"Can't find {root_files[0]}, file doesn't exist", file=sys.stderr)
            continue
        if not file_obj.is_folder():
            raise ValueError(
                f"{file_obj.name} is not a folder. If you are getting files from a non-scRNA task, \
                do not use the --scrna option."
            )
        
        # this folder will have results and checkpoints
        sub_folders = hf.get_all_files_folder(api, file_obj)
        results_folder = None
        for fol in sub_folders:
            if fol.name == "results":
                results_folder = fol
        if not results_folder:
            print(f"ERROR: No results folder found in {file_obj.name}", file=sys.stderr)
            exit(1)

        # get all folder in results_folder
        display_files = hf.get_all_files_folder(api, results_folder)

    # remove folders from display_files
    final_files = []
    for d in display_files:
        if not d.is_folder():
            if debug:
                print(f"Adding {d.name}")
            final_files.append(d)

    return final_files


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
    "--scrna",
    help="If the task is an scRNA task, use this option to get the files",
    is_flag=True,
    default=False,
)
def get_task_files(task_file, task_id, profile, debug, scrna):
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

    files_to_display = []
    if scrna:
        files_to_display = get_scrna_files(api, all_tasks, debug)
    else:
        files_to_display = get_regular_files(api, all_tasks, debug)

    print(f"file_name\tfile_id")
    if len(files_to_display) > 0:
        # format output
        for file in files_to_display:
            print(f"{file.name}\t{file.id}")
    else:
        print("No files found in input task(s)")


if __name__ == "__main__":
    get_task_files()
