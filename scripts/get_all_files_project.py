"""Simple script to get all files in a project"""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
@click.option(
    "--output_file",
    help="Output file to save the list of files",
    default="all_files.txt",
    show_default=True,
)
def get_all_files_project(project, profile, output_file):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)
    project = hf.parse_project(project)
    print(f"Getting all files in project {project}")
    files = hf.get_all_files(api, project)

    with open(output_file, "w", encoding="utf-8") as file:
        file.write("Name\tid\n")
        file.writelines(f"{item.name}\t{item.id}\n" for item in files)

    print(len(files))
    print(len({f.id for f in files}))

if __name__ == "__main__":
    get_all_files_project()
