"""Copy a list of file ids to a taget project."""

import click
import configparser
from pathlib import Path
from sevenbridges import Api
from tqdm import tqdm
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
@click.option(
    "--chunk_size",
    help="Number of files to copy per bulk request",
    default=100,
    show_default=True,
    type=int,
)
@click.option(
    "--skip_existing",
    help="Skip files that already exist by name in the destination project",
    is_flag=True,
    default=False,
    show_default=True,
)
def copy_files(file_ids, profile, project, chunk_size, skip_existing):
    """
    Copy a list of file ids to a new target project.
    """
    # read config file
    api = hf.parse_config(profile)

    project = hf.parse_project(project)

    files = []

    with open(file_ids, "r") as f:
        for line in f:
            files.append(line.strip())

    print(f"Copying files to project: {project}")

    existing_names = None
    if skip_existing:
        existing_names = {f.name for f in hf.get_all_files(api, project) if not f.is_folder()}

    # do copies in chunks
    copy_results = {}
    with tqdm(total=len(files), desc="Copying files", unit="file") as progress:
        for i in range(0, len(files), chunk_size):
            chunk = files[i : i + chunk_size]

            to_copy = chunk
            if skip_existing:
                # look up names for this chunk and skip files already in the project
                records = api.files.bulk_get(files=chunk)
                to_copy = []
                for record in records:
                    if record.resource.name in existing_names:
                        progress.write(f"Skipping {record.resource.id} ({record.resource.name}), already exists in {project}")
                    else:
                        to_copy.append(record.resource.id)

            if to_copy:
                copy_result = api.actions.bulk_copy_files(
                    files=to_copy,
                    destination_project=project,
                )
                copy_results.update(copy_result)
                if skip_existing:
                    existing_names.update(
                        record.resource.name
                        for record in records
                        if record.resource.id in to_copy
                    )

            progress.update(len(chunk))

    for original_file_id, copy_result in copy_results.items():
        print(original_file_id, copy_result)

if __name__ == "__main__":
    copy_files()
