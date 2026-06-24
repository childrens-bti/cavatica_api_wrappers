"""Add metadata to files in a project"""

import click
import re
import pandas as pd
from sevenbridges import Api
from sevenbridges.errors import SbgError
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

# regex for extracting baid from file name:
BAID_RE = re.compile(r"(?<![A-Za-z0-9])(B[AS]_[A-Za-z0-9]{8})(?![A-Za-z0-9])")


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
    required=True,
)
@click.option(
    "--output_file",
    "-o",
    help="Output filename",
    required=True,
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def add_metadata(profile, project, task_file, manifest, output_file, debug):
    """Add metadata to files on Cavatica"""

    project = hf.parse_project(project)

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
        "adapter_sequencing",
    ]
    man_df = man_df.drop(unneeded_cols, errors="ignore", axis=1).drop_duplicates()

    # check manifest for Bioassay_IDs with multiple rows
    duplicate_bioassay_rows = man_df[
        man_df.duplicated(subset=["Bioassay_ID"], keep=False)
    ].sort_values("Bioassay_ID")
    if not duplicate_bioassay_rows.empty:
        duplicate_bioassay_rows.to_csv(
            "Bioassay_ID_multiple_rows.tsv", sep="\t", index=False
        )
        duplicate_ids = ", ".join(duplicate_bioassay_rows["Bioassay_ID"].unique())
        raise ValueError(
            "Manifest contains multiple metadata rows for Bioassay_ID(s): "
            f"{duplicate_ids}. See Bioassay_ID_multiple_rows.tsv"
        )

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

    file_rows = []
    for task in tasks:

        if debug:
            print(task.name)

        if task.status == "COMPLETED":

            # get output files from task
            task_files = get_task_files(task)

            for file in task_files:

                # make sure file actually exists
                try:
                    file_obj = api.files.get(id=file)
                except Exception as e:
                    print(f"Problem retrieving {file.id},{file.name}: {e}")
                    continue

                # try to parse sample name from file name
                match = BAID_RE.search(file.name)
                sample_name = match.group(1) if match else None
                
                if not sample_name:
                    print(f"Could not determine sample_name for {file.id}, {file.name} skipping")
                    continue

                file_rows.append(
                    {
                        "id": file_obj.id,
                        "name": file_obj.name,
                        "project": task.project,
                        "Bioassay_ID": sample_name,
                    }
                )


    # make df out of file rows
    file_df = pd.DataFrame(file_rows)
    file_df = pd.DataFrame(columns=["id", "name", "project", "Bioassay_ID"])

    # Merge metadata to create output manifest
    file_df = pd.merge(file_df, man_df, on="Bioassay_ID")

    if debug:
        print(out_df.columns)
        print(out_df.shape)
    file_df.to_csv(output_file, sep="\t", index=False)


if __name__ == "__main__":
    add_metadata()
