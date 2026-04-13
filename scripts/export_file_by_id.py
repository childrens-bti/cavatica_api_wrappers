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

    Returns: boolean
    """
    exportable = True

    # check if there's files that start with _#
    # these are usually duplicated files
    pattern = r"^_\d"
    if re.match(pattern, file.name):
        # raise ValueError(f"File {file.name}: {file.id} likely a duplicate, please delete or rename before exporting")
        exportable = False

    # check that the file is stored on Cavatica
    if file.storage.type != "PLATFORM":
        # raise ValueError(f"File {file.name}: {file.id} has already been exported to {file.storage.volume}")
        exportable = False

    return exportable


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_ids", help="tsv file with file_id column", required=True)
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
@click.option("--run", help="Run the export job", is_flag=True, default=False)
def export_file_ids(file_ids, profile, volume, location, run):
    """
    Take a task or a list of tasks and export the output data
    to an AWS bucket.
    All files will go to the same bucket/location.
    """
    # read config file
    api = hf.parse_config(profile)
    files_to_export = 0
    print(f"Getting file ids from file: {file_ids}")
    file_id_index = None
    file_name_index = None
    file_location_dict = {}
    with open(file_ids, "r") as f:
        for line in f:
            line_split = line.strip().split("\t")
            if "file_id" in line_split:
                # get the index of the file_id column
                file_id_index = line_split.index("file_id")
                file_name_index = line_split.index("file_name")
            else:
                file_id = line_split[file_id_index]
                file_name = line_split[file_name_index]
                file_split = file_name.split("/")
                file_base_name = file_split[-1]
                file_path = "/".join(file_split[:-1])
                if file_path == "":
                    file_path = location
                try:
                    if file_path not in file_location_dict:
                        file_location_dict[file_path] = []
                    file_location_dict[file_path].append(api.files.get(file_id))
                    files_to_export += 1
                except Exception as e:
                    print(f"Could not find file {file_id}: {e}")

    # loop through files and add any secondary files
    exportable_files = []
    for loc in file_location_dict:
        unique_files = []
        for file in file_location_dict[loc]:

            # check that the file is exportable
            if check_exportable(file):
                exportable_files.append(file)

            if file.secondary_files is not None:
                for secondary in file.secondary_files:
                    if check_exportable(secondary):
                        files_to_export += 1
                        file_location_dict[loc].append(secondary)

            if file not in unique_files:
                unique_files.append(file)
        file_location_dict[loc] = unique_files

    if files_to_export > 0:
        print(f"Exporting {len(exportable_files)} files to {volume}")
        # export files to each location
        for loc in file_location_dict:
            print(f"Exporting {len(file_location_dict[loc])} files to {volume}/{loc}")
            if run:
                print("Running export")
                responses = hf.bulk_export_files(
                    api=api,
                    files=file_location_dict[loc],
                    volume=volume,
                    location=loc,
                    copy_only=False,
                )
                for response in responses:
                    print(response)
                print(f"Successfully exported {len(file_location_dict[loc])} files to {volume}/{loc}")
            else:
                print("Dry run, not exporting")
                print(f"Would export {len(file_location_dict[loc])} files to {volume}/{loc}")
                print(f"Files: {[f.name for f in file_location_dict[loc]]}")
    else:
        print("No files to export")
    print("Done!")


if __name__ == "__main__":
    export_file_ids()
