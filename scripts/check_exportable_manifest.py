"""Script to find exportable files in a manifest"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--manifest", help="Manifest File")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def check_manifest_exportable(manifest, profile):
    """Read a manifest and find exportable files"""
    # read config file
    api = hf.parse_config(profile)

    # read manifest
    with open(manifest, "r") as f:
        line_num = 0
        for line in f:
            if line_num == 0:
                # parse header
                #header_cols = line.strip().split("\t")
                header_cols = line.strip().split(",")
            else:
                # read data lines and get file name
                #line_split = line.strip().split("\t")
                line_split = line.strip().split(",")
                file_id = line_split[header_cols.index("id")]
                file = api.files.get(id=file_id)
                if file.storage.type == "PLATFORM":
                    # make output line
                    out_line = f"{file.name}\t{file.id}\t{file.created_on}"

                    # output to screen
                    print(out_line)

            line_num += 1


if __name__ == "__main__":
    check_manifest_exportable()
