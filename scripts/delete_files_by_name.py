"""Delete files from a list of names"""

import click
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url"
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--files", help="File with filenames to delete", required=True)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def delete_failed_output_files(profile, project, files, run):
    """
    Read files with names to delete, get the file object, and delte the file.
    """

    api = hf.parse_config(profile)

    with open(files, "r") as f:
        for line in f:
            file_name = line.strip()
            file_obj = hf.get_file_obj(api, project, file_name)
            print(f"Deleting file {file_obj.name}: {file_obj.id}")
            if run:
                file_obj.delete()

    print("Done!")


if __name__ == "__main__":
    delete_failed_output_files()
