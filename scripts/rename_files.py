"""Rename files"""

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
@click.option(
    "--files",
    help=" TSV File with filenames to rename, required columns: 'Current Name', 'New Name'",
    required=True,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def delete_failed_output_files(profile, project, files, run):
    """
    Read the file with file names, check if the new name already exists, and rename them.
    """

    api = hf.parse_config(profile)

    # get failed tasks in project
    all_tasks = hf.get_all_tasks(api, project)

    with open(files, "r") as f:
        line_num = 0
        rename_cols = []
        required_cols = ["Current Name", "New Name"]
        for line in f:
            if line_num == 0:
                rename_cols = line.strip().split("\t")
                if not all(x in rename_cols for x in required_cols):
                    print(
                        f"Input file {files} does not contain required columns: {required_cols}"
                    )
                    exit(1)
            else:
                line_split = line.strip().split("\t")
                cur_name = line_split[rename_cols.index("Current Name")]
                new_name = line_split[rename_cols.index("New Name")]

                # get file obj for cur_name
                try:
                    cur_obj = hf.get_file_obj(api, project, cur_name)
                except FileNotFoundError as e:
                    print(f"{cur_name} does not exist, has it already been renamed?")
                    exit(1)

                # check if new_name exists
                try:
                    new_obj = hf.get_file_obj(api, project, new_name)
                except FileNotFoundError as e:
                    print(f"{new_name} not found in {project} proceeding")

                    # rename the file to the new name since it doesn't exist
                    if run:
                        print(f"Renaming {cur_obj.name}")
                        cur_obj.name = new_name
                        cur_obj.save()
                        print(f"File name is now {cur_obj.name}")
                    else:
                        print(
                            f"DRY RUN {cur_obj.name} not renamed to {new_name} but it can be renamed"
                        )

                else:
                    print(f"{new_name} already exists in {project}, skipping")

            line_num += 1

            """
            file_obj = hf.get_file_obj(api, project, file_name)
            print(f"Deleting file {file_obj.name}: {file_obj.id}")
            if run:
                file_obj.delete()
            """

    print("Done!")


if __name__ == "__main__":
    delete_failed_output_files()
