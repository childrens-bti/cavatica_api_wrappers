"""Export files from a list of file ids to an AWS bucket."""

import click
import configparser
import re
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def check_exportable(file):
    """
    Check that a file is exportable

    Inputs:
    - Cavatica file object

    Returns: None
    """
    # check if there's files that start with _#
    # these are usually duplicated files
    if re.match('^_\d', file.name):
        raise ValueError(f"File {file.name}: {file.id} likely a duplicate, please delete or rename before exporting")

    # check that the file is stored on Cavatica
    if file.storage.type != "PLATFORM":
        raise ValueError(f"File {file.name}: {file.id} has already been exported to {file.storage.volume}")


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_ids", help="File with file ids", required=True)
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
def export_file_ids(file_ids, profile, volume, location, run, debug):
    """
    Take a task or a list of tasks and export the output data
    to an AWS bucket.
    All files will go to the same bucket/location.
    """
    # read config file
    api = hf.parse_config(profile)
    files_to_export = []
    print(f"Getting file ids from file: {file_ids}")
    with open(file_ids, "r") as f:
        for line in f:
            file_id = line.strip()
            files_to_export.append(api.files.get(id=file_id))

    if debug:
        print(f"{len(files_to_export)} files to export")

    # loop through files and add any secondary files
    for file in files_to_export:

        # check that the file is exported
        check_exportable(file)

        if file.secondary_files is not None:
            for secondary in file.secondary_files:
                files_to_export.append(secondary)

        # remove duplicates
        files_to_export = list(set(files_to_export))

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
        print("No files to export")


if __name__ == "__main__":
    export_file_ids()
