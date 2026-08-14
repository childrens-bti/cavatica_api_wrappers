import click
from sevenbridges.errors import SbgError
from helper_functions import helper_functions as hf
import pandas as pd
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
CHUNK_SIZE = 100  # API allows up to 100 import items per call


def parse_manifest(manifest_path):
    """
    Parse manifest file combining s3 path and file name columns.

    Inputs:
        manifest_path: str, path to the manifest file (CSV or TSV)
    Returns:
        List of S3 key paths/objects
    """
    # Determine the file type based on the extension
    if manifest_path.endswith(".csv"):
        df = pd.read_csv(manifest_path)
    elif manifest_path.endswith(".tsv"):
        df = pd.read_csv(manifest_path, sep="\t")
    else:
        raise ValueError("Manifest file must be either CSV or TSV format.")

    # Check for required columns
    required_columns = ["file_name", "aws_s3_path"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Manifest file is missing required column: {col}")

    # Combine s3_path and file_name to create full S3 key paths
    s3_keys = df.apply(lambda row: f"{row['aws_s3_path'].rstrip('/')}/{row['file_name']}", axis=1).tolist()
    
    # remove 's3://bucket-name/' from keys
    s3_keys = [key.split('/', 3)[-1] for key in s3_keys]

    return s3_keys


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
    "--manifest",
    help="Path to a manifest file (CSV or TSV) containing S3 keys and metadata. If provided, the script will read S3 keys from the manifest instead of a separate text file.",
)
@click.option(
    "--run",
    is_flag=True,
    default=False,
    help="Actually submit the imports. Without this flag, the script only does a dry run.",
)
def bulk_import(project, volume, s3_keys_file, profile, manifest, run):
    """
    Bulk import files from an S3-backed volume into a Cavatica project.
    The script reads S3 keys from a text file, groups them into batches of 100,
    and submits each batch with api.imports.bulk_submit().
    """
    api = hf.parse_config(profile)
    project = hf.parse_project(project)

    if manifest and s3_keys_file:
        raise ValueError("Please provide either a manifest file or an S3 keys file, not both.")
    elif s3_keys_file:    
        s3_keys = load_s3_keys(s3_keys_file)
    elif manifest:
        s3_keys = parse_manifest(manifest)
    else:
        raise ValueError("Please provide either a manifest file or an S3 keys file.")

    all_items = [build_import_item(volume, key, project) for key in s3_keys]
    chunks = list(chunk_list(all_items, CHUNK_SIZE))

    click.echo(f"Loading {len(s3_keys)} S3 key(s).")
    click.echo(f"Prepared {len(chunks)} chunk(s).")

    if not run:
        click.echo("[dry-run] Nothing was submitted.")
        return

    for i, chunk in enumerate(tqdm(chunks, desc="Submitting chunks", unit="chunk"), start=1):
        click.echo(f"Submitting chunk {i}/{len(chunks)} with {len(chunk)} item(s)...")
        try:
            api.imports.bulk_submit(imports=chunk)
        except SbgError as e:
            click.echo(f"[error] Chunk {i} failed: {e}")

    click.echo("Done.")


if __name__ == "__main__":
    bulk_import()
