"""Simple script to find a file in a project"""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_name", help="File name")
@click.option("--project", help="Project ID")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_file(file_name, project, profile):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)
    print(f"Searching for file {file_name} in project {project}")
    file_obj = hf.get_file_obj(api, project, file_name)
    print(file_obj.id)
    print(file_obj.name)
    #print(file_obj.storage.type)

if __name__ == "__main__":
    find_file()
