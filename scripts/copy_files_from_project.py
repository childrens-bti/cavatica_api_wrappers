"""Copy a file to a new project."""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--manifest",
    help="TSV file with columns 'id' and 'name",
    default="COMPLETED",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def copy_files(project, profile, manifest, run):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    project = hf.parse_project(project)

    with open(manifest, "r") as f:
        line_num = 0
        files_to_copy = []
        for line in f:
            if line_num == 0:
                # parse header
                header_cols = line.strip().split("\t")
            else:
                # read data lines and get file name and id
                line_split = line.strip().split("\t")
                file_id = line_split[header_cols.index("id")]
                file_name = line_split[header_cols.index("name")]

                if "/" in file_name:
                    file_name = file_name.split("/")[1]

                # get the file
                file_obj = api.files.get(id=file_id)

                # check that the file names match
                # this is just in case the ids in the manifest aren't cavatica ids
                if file_name != file_obj.name:
                    raise ValueError(f"file name in manifest: {file_name} does not match file name in Cavatica {file_obj.name}")
                else:
                    # check if the file is already loaded to the project
                    try:
                        new_obj = hf.get_file_obj(api, project, file_name)
                    except FileNotFoundError as e:
                        files_to_copy.append(file_id)
            
            if line_num % 100 == 0:
                print(f"Processed {line_num} lines")

            line_num += 1

    if run and len(files_to_copy) > 0:
        print(f"Copying files to project: {project}")
        copy_results = api.actions.bulk_copy_files(
            files=files_to_copy,
            destination_project=project,
        )

        for original_file_id, copy_result in copy_results.items():
            print(original_file_id, copy_result)
    else:
        print(f"Dry run, {len(files_to_copy)} ready to be copied to {project}")

    print("Done!")


if __name__ == "__main__":
    copy_files()
