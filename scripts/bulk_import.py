import click
from sevenbridges.errors import SbgError
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
CHUNK_SIZE = 100  # API allows up to 100 import items per call


def load_s3_keys(file_path):
    """Read S3 key paths/objects from a text file, one per line."""
    with open(file_path) as f:
        return [line.strip() for line in f if line.strip()]


def chunk_list(items, size):
    """Split a list into chunks of up to 100 items."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_import_item(volume, s3_key_object, project):
    return {
        "volume": volume,
        "location": s3_key_object,
        "project": project,
    }


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--project",
    required=True,
    help="Destination Cavatica project, for example: childrens-bti/cavatica-bulk-import-dev",
)
@click.option(
    "--volume",
    required=True,
    help="Cavatica volume name associated with your S3 bucket",
)
@click.option(
    "--s3-keys-file",
    "s3_keys_file",
    required=True,
    type=click.Path(exists=True),
    help=(
        "Text file containing S3 object keys (file paths), one per line. This is NOT an AWS authentication/access key , use S3 object paths (e.g. path/within/volume/file.raw)."
    ),
)
@click.option(
    "--profile",
    default="cavatica",
    show_default=True,
    help="Credentials profile to use e.g. cavatica or turbo",
)
@click.option(
    "--run",
    is_flag=True,
    default=False,
    help="Actually submit the imports. Without this flag, the script only does a dry run.",
)
def bulk_import(project, volume, s3_keys_file, profile, run):
    """
    Bulk import files from an S3-backed volume into a Cavatica project.
    The script reads S3 keys from a text file, groups them into batches of 100,
    and submits each batch with api.imports.bulk_submit().
    """
    api = hf.parse_config(profile)
    project = hf.parse_project(project)

    s3_keys = load_s3_keys(s3_keys_file)
    all_items = [build_import_item(volume, key, project) for key in s3_keys]
    chunks = list(chunk_list(all_items, CHUNK_SIZE))

    click.echo(f"Loading {len(s3_keys)} S3 key(s).")
    click.echo(f"Prepared {len(chunks)} chunk(s).")

    if not run:
        click.echo("[dry-run] Nothing was submitted.")
        return

    for i, chunk in enumerate(chunks, start=1):
        click.echo(f"Submitting chunk {i}/{len(chunks)} with {len(chunk)} item(s)...")
        try:
            api.imports.bulk_submit(imports=chunk)
        except SbgError as e:
            click.echo(f"[error] Chunk {i} failed: {e}")

    click.echo("Done.")


if __name__ == "__main__":
    bulk_import()
