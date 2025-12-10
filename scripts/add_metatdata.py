"""Add metadata to files in a project"""

import click
import numpy as np
import pandas as pd
from sevenbridges import Api
from sevenbridges.errors import SbgError
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def get_task_files(task) -> list:
    """
    Get files from a task.

    Input:
    - task: SBG task object

    Returns:
    - list of file ids
    """

    files = []

    for out_key in task.outputs.keys():
        if type(task.outputs[out_key]) is list:
            for file in task.outputs[out_key]:
                if type(file) is list:
                    for f in file:
                        if f is not None:
                            files.append(f)
                else:
                    if file is not None:
                        files.append(file)
        else:
            if task.outputs[out_key] is not None:
                files.append(task.outputs[out_key])

    return files


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--project", help="Project ID")
@click.option("--task_file", help="File with task ids")
@click.option(
    "--manifest",
    "-m",
    help="Input Manifest file",
)
@click.option(
    "--output_file",
    "-o",
    help="Output filename",
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def add_metadata(profile, project, task_file, manifest, output_file, debug):
    """Add metadata to files on Cavatica"""

    # different "sample name" fields
    sample_fields = [
        "sample_name",
        "biospecimen_name",
        "tumor_name",
        "sample_id",
    ]

    # read config file
    api = hf.parse_config(profile)

    # read manifest file
    man_df = pd.read_csv(manifest, sep="\t", keep_default_na=False)

    # strip some columns related to file name and read info
    unneeded_cols = [
        "file_name",
        "file_format",
        "file_hash_type",
        "file_size",
        "file_hash_value",
        "read_pair_number",
        "lane_number",
        "flow_cell_barcode",
        "reference_genome",
        "mean_coverage",
        "project",
    ]
    man_df = man_df.drop(unneeded_cols, axis=1).drop_duplicates()

    if debug:
        print(man_df.columns)
        print(man_df.shape)

    # get all tasks or a list of tasks in a project
    tasks = []
    if project and task_file:
        raise ValueError("Either 'project' or 'task_file' must be set. Not Both.")
    elif project:
        tasks = hf.get_all_tasks(api, project)
    elif task_file:
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                task = api.tasks.get(id=task_id)
                tasks.append(task)
    else:
        raise ValueError("Either 'project' or 'task_file' must be set.")

    out_df = pd.DataFrame()

    for task in tasks:

        if debug:
            print(task.name)

        if task.status == "COMPLETED":
            # get the sample name from the task
            sample_name = None
            matches = [task.inputs[key] for key in sample_fields if key in task.inputs]
            if len(matches) == 0:
                print(f"Task {task.name} has no sample name-like field, skipping")
                continue
            elif len(matches) != 1:
                raise ValueError(f"Expected exactly one match, got {len(matches)}")
            sample_name = matches[0]

            # look up that sample name in the manifest
            metadata_row = man_df.loc[man_df["Bioassay_ID"] == sample_name].copy()

            if metadata_row.shape[0] > 1:
                raise ValueError(f"{sample_name} has multiple values in {manifest}")

            task_df = pd.DataFrame(columns=["id", "name", "project"])

            # get output files from task
            task_files = get_task_files(task)

            for file in task_files:

                # make sure file actually exists
                try:
                    file_obj = api.files.get(id=file)
                except Exception as e:
                    print(f"Problem retrieving {file.id},{file.name}: {e}")
                    continue

                task_df.loc[len(task_df)] = {
                    "id": file.id,
                    "name": file.name,
                    "project": task.project,
                }

            # make a metadata manifest that I can upload to Cavatica

            # Add a temp key to both task_df and metadata_row
            task_df["key"] = 1
            metadata_row["key"] = 1

            # Merge on the temp key and drop it
            task_df = pd.merge(task_df, metadata_row, on="key").drop("key", axis=1)

            # Add task results to main output
            out_df = pd.concat([out_df, task_df])

    if debug:
        print(out_df.columns)
        print(out_df.shape)
    out_df.to_csv(output_file, sep="\t", index=False)


if __name__ == "__main__":
    add_metadata()
