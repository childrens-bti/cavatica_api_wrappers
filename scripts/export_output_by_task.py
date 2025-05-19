"""Export files from a list of tasks to an AWS bucket."""

import click
import configparser
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def check_and_get_files(api, task_id):
    """
    Check that a task is COMPLETED and export data.
    Inputs:
    - api object
    - task id

    Returns:
    - if the task is succesful: a list of output file ids
    """
    files = []
    print(f"Current task id: {task_id}")
    task = api.tasks.get(id=task_id)
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
        print(f"{task} is a draft task and has not run yet, skipping")
    elif task.status == "RUNNING":
        print(f"{task} is currently running, skipping")
    elif task.status == "FAILED":
        print(f"{task} has failed, skipping")
    else:
        print(f"{task} is in an unknown state: {task.status}")
        print("Please check the task status and try again, skipping")

    return files


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--task_file", help="File with task ids")
@click.option("--task_id", help="Task id")
@click.option(
    "--volume", help="username/volume_name of volume to export to.", required=True
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option(
    "--location",
    help="Bucket prefix to export data to (for example: volume/folder/sub-folder)",
    default="harmonized",
    show_default=True,
    required=True,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def export_task_outputs(task_file, task_id, profile, volume, location, run, debug):
    """
    Take a task or a list of tasks and export the output data
    to an AWS bucket.
    All files from all tasks will go to the same bucket/location.
    """
    # read config file
    api = hf.parse_config(profile)
    files_to_export = []
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id")
        exit(1)
    elif task_id:
        files_to_export = check_and_get_files(api, task_id)
    elif task_file:
        print(f"Getting tasks from file: {task_file}")
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                files_to_export.extend(check_and_get_files(api, task_id))

                if debug:
                    print(f"{len(files_to_export)} files to export")

    # loop through files and add any secondary files, and check that both files exist
    for file in files_to_export:
        try:
            file_obj = api.files.get(id=file)
        except NotFound as e:
            print(f"Can't export {file.name}, file doesn't exist")

        if file.secondary_files is not None:
            for secondary in file.secondary_files:
                try:
                    file_obj = api.files.get(id=secondary)
                except NotFound as e:
                    print(f"Can't export {file.name}, file doesn't exist")
                # check if secondary already in list
                if secondary not in files_to_export:
                    files_to_export.append(secondary)

    if debug:
        print(f"Preparing to export the following files:")
        for file in files_to_export:
            print(f"{file.name}: {file.id}")

    if len(files_to_export) > 0:
        print(f"Exporting {len(files_to_export)} files to {volume}/{location}")
        if run and not debug:
            print("Running export")
            responses = hf.bulk_export_files(
                api=api,
                files=files_to_export,
                volume=volume,
                location=location,
                copy_only=False,
            )
            for response in responses:
                print(response)
            print("Export complete")
        else:
            print("Dry run, not exporting")
    else:
        print("No files to export, exiting")
        exit(0)


if __name__ == "__main__":
    export_task_outputs()
