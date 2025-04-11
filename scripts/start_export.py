"""Start exporting files from Cavatica to AWS"""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def bulk_export_files(api, files, volume, location, overwrite=True, copy_only=False):
    """
    Exports list of files to volume in bulk
    """

    chunk_size = 100  # Max legal bulk size for export is 100 items.
    final_responses = []

    def is_finished(response):
        return response in ["COMPLETED", "FAILED", "ABORTED"]

    def error_handling_after_completion(responses):
        errors = [
            s.resource.error.message for s in responses if s.resource.state == "FAILED"
        ]
        if errors:
            data = [
                s.resource.error if s.resource.state == "FAILED" else s.resource.result
                for s in responses
            ]
            raise Exception(
                "There were errors with bulk exporting.\n"
                + "\n".join([str(d) for d in data])
            )

    def error_handling_after_submission(responses):
        errors = [s.error.message for s in responses if not s.valid]
        if errors:
            data = [s for s in responses if not s.valid]

            raise Exception(
                "There were errors with bulk submission.\n"
                + "\n".join(
                    [
                        f"<Error: status={s.error.status}, code={s.error.code}>; "
                        f"{s.error.message}"
                        for s in data
                    ]
                )
            )

    # export files in batches of 100 files each
    for i in range(0, len(files), chunk_size):

        # setup list of dictionary with export requests
        exports = [
            {
                "file": f,
                "volume": volume,
                "location": location + "/" + f.name,
                "overwrite": overwrite,
            }
            for f in files[i : i + chunk_size]
        ]

        # initiate bulk export of batch and wait until finished
        responses = api.exports.bulk_submit(exports, copy_only=copy_only)

        # check for errors in bulk submission
        error_handling_after_submission(responses)

        # wait for bulk job to finish
        while not all(is_finished(s.resource.state) for s in responses):
            time.sleep(10)
            responses = api.exports.bulk_get([s.resource for s in responses])

        # check if each job finished successfully
        error_handling_after_completion(responses)

        final_responses.extend(responses)

    return final_responses


# this function won't really work because of the rate limit
@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--file_name", help="File name")
@click.option("--volume", help="username/volume_name of volume to export to.")
@click.option(
    "--location",
    help="Bucket prefix to export data to (for example: volume/folder/sub-folder)",
    default="harmonized",
    show_default=True,
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def launch_export(profile, file_name, volume, location):
    """
    Export a list of files from a manifest from Cavatica to AWS
    """
    # read config file
    api = hf.parse_config(profile)

    # open file and read it
    line_num = 0
    id_col = None
    file_name_col = None
    project_col = None
    files_to_export = []
    with open(file_name, "r") as f:
        for line in f:

            if line_num == 0:
                # process header
                cols = line.strip().split(",")
                for col in cols:
                    if col == "id":
                        id_col = cols.index(col)
                    elif col == "name":
                        file_name_col = cols.index(col)
                    elif col == "project":
                        project_col = cols.index(col)
                if id_col is None:
                    print("Id column not defined, trying to use file and project name")
                    if file_name_col is None or project_col is None:
                        print(
                            "ERROR: Either file id or file and project name columns must be in manifest"
                        )
                        exit(1)

            else:
                file_obj = None
                cols = line.strip().split(",")
                if id_col is not None:
                    file_obj = api.files.get(cols[id_col])
                else:
                    # look up file id based on name
                    file_obj = hf.get_file_obj(
                        api, cols[project_col], cols[file_name_col]
                    )
                files_to_export.append(file_obj)

            line_num += 1
    
    print(f"Exporting {len(files_to_export)} files to {volume}/{location}")
    print("Files to export:")
    for file in files_to_export:
        print(file.name)
    responses = bulk_export_files(
        api=api,
        files=files_to_export,
        volume=volume,
        location=location,
        copy_only=False,
    )
    for response in responses:
        print(response)
    print("Export complete")


if __name__ == "__main__":
    launch_export()
