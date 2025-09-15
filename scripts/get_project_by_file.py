"""Get the project that a file is in."""

import sys
import click
import configparser
import re
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_names", help="File with filenames")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def get_project_by_task(file_names, profile):
    """
    Find the project a file is in.
    """
    # read config file
    api = hf.parse_config(profile)

    # get all projects I have access to
    all_projects = hf.get_all_projects(api)

    """
    for proj in all_projects:
        proj_obj = api.projects.get(id=proj)
        print(proj_obj.name)
        print(proj_obj.id)
        exit()
    """

    # read file with file names
    with open(file_names, "r") as f:
        for line in f:
            processed_line = line.strip()
            print(f"Searching all projects for {processed_line}")
            file_obj = None

            # search projects for file
            for proj in all_projects:
                proj_obj = api.projects.get(id=proj)
                # only use CNMC projects
                org = proj_obj.id.split("/")[0]
                if org == "d3b-bixu-ops" or proj_obj.name == "pbta-rmats-reruns":
                    continue
                try:
                    file_obj = hf.get_file_obj(api, proj, processed_line)
                except Exception as e:
                    pass
                if file_obj is not None:
                    print(f"File in {proj_obj.id}")
                    break

    """
    old stuff
    # get all of the tasks either from --task_id or reading the --task_file file
    all_tasks = []
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id")
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
                print(f"Can't find {file}, file doesn't exist")

            if file.secondary_files is not None:
                for secondary in file.secondary_files:
                    try:
                        file_obj = api.files.get(id=secondary)
                    except NotFound as e:
                        print(f"Can't find {file.name}, file doesn't exist")
                    # check if secondary already in list
                    if secondary not in files_to_display:
                        files_to_display.append(secondary)

        if len(files_to_display) > 0:
            # format output
            for file in files_to_display:
                try:
                    print(f"{file.name}\t{file.id}")
                except Exception as e:
                    print(f"Something happened for {file}: {e}")
        else:
            print("No files found in input task(s)")
    """


if __name__ == "__main__":
    get_project_by_task()
