"""Delete files from a list of file IDs"""

import click
import time
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from tqdm import tqdm
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--files", help="File with filenames to delete", required=True)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def delete_failed_output_files(profile, files, run):
    """
    Read files with names to delete, get the file object, and delte the file.
    """

    api = hf.parse_config(profile)

    all_ids = []

    with open(files, "r") as f:
        for line in f:
            file_id = line.strip()
            all_ids.append(file_id)

    # split files into chunks of 100
    chunk_size = 100
    chunks = [all_ids[i : i + chunk_size] for i in range(0, len(all_ids), chunk_size)]

    count = 0

    if run:
        print("Delteting files...")
    else:
        print("Dry run mode. No files will be deleted.")

    # use bulk deletion to delete files by chunk
    for chunk in tqdm(chunks):
        if run:
            try:
                count += len(chunk)
                api.files.bulk_delete(files=chunk)
                #print(f"Deleted {len(chunk)} files. {count} / {len(all_ids)}")
            except NotFound as e:
                print(f"Error deleting files: {e}")
        else:
            #print(f"Would delete {len(chunk)} files. Use --run to execute.")
            time.sleep(0.01)

    print("Done!")


if __name__ == "__main__":
    delete_failed_output_files()
