"""Add metadata to files in a project"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def add_file_metadata(f, meta_fields, file_baid) -> None:
    """
    Add metadata to a file.

    Inputs:
    - f: Sevenbridges file object
    - meta_fields: dictionary with bioassay id metadata
    """
    for m in meta_fields[file_baid]:
        f.metadata[m] = meta_fields[file_baid][m]

    f.save()


def process_manifest(manifest) -> dict:
    """
    Read manifest file and return dictionary of required metadata fields

    Input:
    - manifest file

    Returns:
    - dict
    """
    meta_fields = {}
    required_fields = [
        "external_sample_id",
        "sample_type",
        "composition",
        "experimental_strategy",
        "Bioassay_ID",
    ]
    with open(manifest, "r") as man:
        line_num = 0
        my_cols = []
        for line in man:
            if line_num == 0:
                my_cols = line.strip().split("\t")
                if not set(required_fields).issubset(set(my_cols)):
                    raise ValueError(
                        f"{manifest} missing one or more required field: {required_fields}"
                    )
            else:
                line_split = line.strip().split("\t")
                baid = line_split[my_cols.index("Bioassay_ID")]
                if baid not in meta_fields.keys():
                    meta_fields[baid] = {}
                for field in required_fields:
                    my_meta = line_split[my_cols.index(field)]
                    if field not in meta_fields[baid].keys():
                        meta_fields[baid][field] = my_meta
                    else:
                        if meta_fields[baid][field] != my_meta:
                            raise ValueError(
                                f"Conflicting values in manifest for {baid} in {field}"
                            )

            line_num += 1

    return meta_fields


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option("--manifest", help="Input manifest file")
@click.option(
    "--sample_dict",
    help="Optional input file with file names and corresponding Bioassay ID",
)
@click.option(
    "--all",
    is_flag=True,
    default=False,
    help="Optional, try to assign metadata to all files in project. Assumes Bioassay ID is in file names",
)
@click.option(
    "--file_name", help="Optional input file name; only for adding custom metadata"
)
@click.option(
    "--custom",
    help="Custom key:value metadata to add; only used with file_name option ",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def add_metadata(
    project, manifest, sample_dict, all, file_name, custom, profile, debug
):
    """Main function to add metadata in different ways"""
    # read config file
    api = hf.parse_config(profile)

    # check option compatibility
    defined_count = 0
    for o in (all, sample_dict, file_name):
        if o:
            defined_count += 1

    if defined_count == 0:
        raise ValueError(
            "No options set. Needs one of all, sample_dict, or file_name. See help message."
        )
    elif defined_count > 1:
        raise ValueError(
            "Multiple options set. Only one of all, sample_dict, or file_name can be set. See help message."
        )
    elif file_name or custom and not (file_name and custom):
        raise ValueError(
            "When using file_name or custom metadata, both options must be set."
        )

    meta_fields = process_manifest(manifest)

    if debug:
        print(meta_fields)

    all_files = []
    # TODO: implement custom and all options
    if file_name and custom:
        raise NotImplementedError("File_name and custom metadata not implemented yet")
    elif sample_dict:
        # read the sample_dict file, get files, and which baid they're associated with
        required_fields = ["file_name", "Bioassay_ID"]
        with open(sample_dict, "r") as sam:
            line_num = 0
            my_cols = []
            for line in sam:
                if line_num == 0:
                    my_cols = line.strip().split("\t")
                    if not set(required_fields).issubset(set(my_cols)):
                        raise ValueError(
                            f"{manifest} missing one or more required field: {required_fields}"
                        )
                else:
                    line_split = line.strip().split("\t")
                    baid = line_split[my_cols.index("Bioassay_ID")]
                    my_file = line_split[my_cols.index("file_name")]
                    file_obj = hf.get_file_obj(api, project, my_file)
                    add_file_metadata(file_obj, meta_fields, baid)

                line_num += 1

    elif all:
        raise NotImplementedError("Adding metadata to all files not implemented yet")


if __name__ == "__main__":
    add_metadata()
