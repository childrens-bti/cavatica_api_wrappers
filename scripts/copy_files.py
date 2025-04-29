"""Copy a list of file ids to a taget project."""

import click
import configparser
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_ids", help="File with file ids")
@click.option("--project", help="Project name to copy files to")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def copy_files(file_ids, profile, project):
    """
    Copy a list of file ids to a new target project.
    """
    # read config file
    api = hf.parse_config(profile)

    files = []

    with open(file_ids, "r") as f:
        for line in f:
            files.append(line.strip())

    print(f"Copying files to project: {project}")
    copy_results = api.actions.bulk_copy_files(
        files=files,
        destination_project=project,
    )

    for original_file_id, copy_result in copy_results.items():
        print(original_file_id, copy_result)

if __name__ == "__main__":
    copy_files()
