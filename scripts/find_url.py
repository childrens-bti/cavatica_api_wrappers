"""Simple script to find a file in a project"""

import os
import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--id", help="File name")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_file(id, profile):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    my_url = "https://cavatica.sbgenomics.com/u/"

    try:
        task = api.tasks.get(id=id)
        my_url = f"{my_url}{task.project}/tasks/{id}"
    except Exception as e:
        try:
            file = api.files.get(id=id)
            my_url = f"{my_url}{file.project}/files/{id}"
        except Exception as e:
            print(f"Input id: {id} is neither an existing task or file.")
            exit(1)

    print(my_url)
    os.system(f"open {my_url}")

if __name__ == "__main__":
    find_file()
