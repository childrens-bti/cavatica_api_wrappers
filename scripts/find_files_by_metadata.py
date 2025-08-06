"""Script to get a list of files with search metadata"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--metadata", help="Column name with metadata key to lookup")
@click.option("--project", help="Project ID")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--in_file", help="Input tsv file with metadata values to look up")
def find_file(metadata, project, profile, in_file):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    # get all of the files in the project
    all_files = hf.get_all_files(api, project)

    # reformat all files by metadata to be more easily searched
    meta_dict = {}
    for file in all_files:
        if file.metadata[metadata] in meta_dict:
            meta_dict[file.metadata[metadata]].append(file.name)
        else:
            meta_dict[file.metadata[metadata]] = [file.name]

    with open(in_file, "r") as f:
        line_num = 0
        my_cols = []
        for line in f:
            if line_num == 0:
                my_cols = line.strip().split("\t")
                if not metadata in my_cols:
                    print(
                        f"Input file {in_file} does not contain metadata column: {metadata}"
                    )
                    exit(1)
            else:
                line_split = line.strip().split("\t")
                my_meta = line_split[my_cols.index(metadata)]
                if my_meta in meta_dict:
                    my_files = meta_dict[my_meta]
                    for fil in my_files:
                        print(f"{my_meta}\t{fil}")
            
            line_num += 1


if __name__ == "__main__":
    find_file()
