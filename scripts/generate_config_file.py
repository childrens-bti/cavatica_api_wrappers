"""Generate a JSON configuration for a cohort RNA-seq run.

The manifest is currently the source of cohort metadata.  The input format is
deliberately forgiving because both full manifests and the smaller rerun
"mini manifests" are tabular files with the same metadata columns.
"""

import csv
import json
import re
from pathlib import Path

import click
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

# These are the standard references used by the RNA-seq workflow.  Keep this
# table here until the references can be looked up from DW.
STANDARD_REFERENCES = {
    "human": {},
    "mouse": {
        "RNAseQC_GTF_stranded": "gencode.vM38.primary_assembly.rnaseqc.stranded.gtf",
        "RNAseQC_GTF_unstranded": "gencode.vM38.primary_assembly.rnaseqc.unstranded.gtf",
        "RSEMgenome": "RSEM_GRCm39_GENCODE38.tar.gz",
        "STARgenome": "STAR_GRCm39_GENCODE38.tar.gz",
        "gtf_anno": "gencode.vM38.primary_assembly.annotation.gtf",
        "kallisto_idx": "RSEM_GRCm39_GENCODE38.transcripts.kallisto.idx",
        "reference_fasta": "GRCm39.vM38.primary_assembly.genome.fa",
    },
}

ORGANISM_ALIASES = {
    "homo sapiens": "human",
    "human": "human",
    "mus musculus": "mouse",
    "mouse": "mouse",
}


def parse_app_id(app_id):
    """Validate an app ID and require its revision component."""
    parts = app_id.strip("/").split("/")
    if len(parts) != 4 or not all(parts):
        raise click.ClickException(
            "--app_id must be user/project/app/revision; the revision is required"
        )
    if not re.fullmatch(r"\d+", parts[3]):
        raise click.ClickException("The app revision in --app_id must be an integer")
    return "/".join(parts)


def read_manifest(path):
    """Read a CSV or TSV manifest without loading it into a data-frame."""
    try:
        with path.open(newline="") as handle:
            header = handle.readline()
            handle.seek(0)
            delimiter = "\t" if "\t" in header else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                raise click.ClickException("Manifest has no header")
            rows = [
                {key.strip(): (value or "").strip() for key, value in row.items()}
                for row in reader
                if any((value or "").strip() for value in row.values())
            ]
    except csv.Error as exc:
        raise click.ClickException(f"Could not parse manifest {path}: {exc}") from exc
    if not rows:
        raise click.ClickException(f"Manifest contains no data rows: {path}")
    return rows


def values(rows, column):
    """Return meaningful, case-normalized values from a manifest column."""
    return {
        value.strip().casefold()
        for row in rows
        if (value := row.get(column, "").strip())
        and value.casefold() not in {"na", "n/a", "none", "unknown"}
    }


def infer_organism(rows, pdx=False):
    organisms = values(rows, "organism")
    # PDX manifests can contain both human grafts and mouse control/cell-line
    # material.  The workflow references must follow the graft organism.
    if pdx and "homo sapiens" in organisms:
        return "human"
    if len(organisms) != 1:
        raise click.ClickException(
            "Manifest must contain exactly one non-empty organism value; "
            f"found {sorted(organisms) or 'none'}"
        )
    try:
        return ORGANISM_ALIASES[next(iter(organisms))]
    except KeyError as exc:
        raise click.ClickException(
            f"Unsupported organism {next(iter(organisms))!r}; supported organisms are "
            "Homo sapiens and Mus musculus"
        ) from exc


def infer_pdx(rows):
    """Identify PDX cohorts using an explicit column or standard metadata."""
    explicit = values(rows, "pdx")
    if explicit and not explicit <= {"true", "false", "0", "1", "yes", "no"}:
        raise click.ClickException("The pdx column must contain boolean values")
    if explicit and len(explicit) > 1:
        raise click.ClickException("Manifest contains conflicting pdx values")
    if explicit:
        return next(iter(explicit)) in {"true", "1", "yes"}

    metadata = " ".join(
        value
        for row in rows
        for column in ("composition", "tumor_descriptor", "sample_type")
        if (value := row.get(column, "").casefold())
    )
    return "xenograft" in metadata or "pdx" in metadata


def build_config(rows, app_id):
    """
    Build the config json.
    """
    pdx = infer_pdx(rows)
    if pdx and app_id.split("/")[2] != "cnh-pdx-classification":
        raise click.ClickException(
            "PDX manifests must use the cnh-pdx-classification workflow"
        )
    organism = infer_organism(rows, pdx=pdx)
    config = {
        "app": app_id,
        "organism": organism,
        "pdx": pdx,
        **STANDARD_REFERENCES[organism],
    }
    if organism != "human":
        config |= {
            "run_t1k": False,
            "run_rmats": False,
            "run_fusions": False,
        }
    return config


def get_human_refs_from_app(app):
    """Add suggested file inputs from an app to the human references."""
    for app_input in app.raw.get("inputs", []):
        input_type = app_input.get("type", "")
        if "File" not in str(input_type):
            continue
        suggested = app_input.get("sbg:suggestedValue")
        if isinstance(suggested, list):
            suggested = suggested[0] if suggested else None
        if isinstance(suggested, dict):
            suggested = suggested.get("name") or suggested.get("path")
        if not suggested:
            continue
        input_id = app_input["id"].rsplit("#", 1)[-1]
        STANDARD_REFERENCES["human"][input_id] = str(suggested).rsplit("/", 1)[-1]


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--app_id",
    required=True,
    help="CAVATICA app ID including revision: user/project/app/revision",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output JSON path (default: <manifest-stem>_config.json)",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
def generate_config(manifest, app_id, output, profile):
    """Generate a prepopulated JSON config from MANIFEST."""

    app_id = parse_app_id(app_id)
    project_id = "/".join(app_id.split("/")[:2])
    try:
        api = hf.parse_config(profile)
        api.projects.get(id=project_id)
    except Exception as exc:
        raise click.ClickException(
            f"Unable to find or access Cavatica project {project_id!r}: {exc}"
        ) from exc
    try:
        app = api.apps.get(id=app_id)
    except Exception as exc:
        raise click.ClickException(
            f"Unable to find or access Cavatica app {app_id!r}: {exc}"
        ) from exc

    get_human_refs_from_app(app)

    config = build_config(read_manifest(manifest), app_id)
    output = output or Path.cwd() / f"{manifest.stem}_config.json"
    output.write_text(json.dumps(config, indent=2) + "\n")
    click.echo(f"Wrote {output}")


if __name__ == "__main__":
    generate_config()
