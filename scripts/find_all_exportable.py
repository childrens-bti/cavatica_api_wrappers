"""Script to get a list of files that are exportable from a project"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
LIMIT = 50

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_file(project, profile):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    # get all of the files in the project
    all_files = hf.get_all_files(api, project)
    print(f"Found {len(all_files)} files in project {project}")

    # check each file's storage.type
    for file in all_files:

        if file.id == "68d709388f828964f23ef782":
            print("found our file")
            print(file.storage.type)

        # check if it's a folder
        if file.is_folder() == True:
            continue

        if file.storage.type == "PLATFORM":
            # make output line
            out_line = f"{file.name}\t{file.id}\t{file.created_on}"

            # output to screen
            print(out_line)
        else:
            print(f"Skipping non-exportable file {file.name} ({file.id}) with storage type {file.storage.type}")


if __name__ == "__main__":
    find_file()
