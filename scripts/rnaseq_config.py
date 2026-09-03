"""Offline validation for minimal CNH RNA-seq configuration files.

This module deliberately does not contact CAVATICA.  It validates the small
reviewed configuration artifact and, when given a manifest, checks only the
fields required to form safe per-Bioassay task input groups.
"""

from __future__ import annotations

import csv
import configparser
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ID_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
APP_ID_RE = re.compile(r"^[^/\s]+/[^/\s]+/[^/\s]+(?:/[^/\s]+)?$")
ADAPTER_RE = re.compile(r"^[ACGTN]+$", re.IGNORECASE)
ALLOWED_STRANDNESS = {"default", "fr-stranded", "rf-stranded"}
CONFIG_METADATA_TYPES = {
    "organism": "enum",
    "pdx": "bool",
    "experimental_strategy": "enum",
}
CONFIG_METADATA_ENUMS = {
    "organism": {"human", "mouse"},
    "experimental_strategy": {"rna-seq", "ribo-seq"},
}
REQUIRED_MANIFEST_COLUMNS = {
    "Bioassay_ID",
    "file_name",
    "file_format",
    "is_paired_end",
    "read_pair_number",
}
ORGANISM_COLUMNS = {"organism", "host_organism"}
WORKFLOW_REPOSITORY = "childrens-bti/kf-rnaseq-workflow-cnh"
GITHUB_MASTER_COMMIT_URL = (
    "https://api.github.com/repos/"
    f"{WORKFLOW_REPOSITORY}/commits/master"
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    source: str | None = None
    row: int | None = None
    bioassay_id: str | None = None

    def format(self) -> str:
        location = []
        if self.source:
            location.append(self.source)
        if self.row:
            location.append(f"row {self.row}")
        if self.bioassay_id:
            location.append(f"Bioassay_ID={self.bioassay_id}")
        suffix = f" ({', '.join(location)})" if location else ""
        return f"{self.severity.upper()} [{self.code}]{suffix}: {self.message}"


@dataclass(frozen=True)
class VersionProfile:
    app_base: str
    allowed_overrides: dict[str, str]
    reference_profiles: frozenset[str]


def _schema(keys: str, value_type: str) -> dict[str, str]:
    """Build a CWL input-name to JSON-value-type mapping."""
    return {key: value_type for key in keys.split()}


# Snapshot of every top-level input in kfdrc_RNAseq_workflow.cwl at
# 7f9efacc9786943009ff5085698d6025cb78719d.  File values are CAVATICA file
# identifiers/names; offline validation can only establish that they are
# nonempty strings, not that the project contains them.
OVERRIDE_TYPES: dict[str, str] = {}
OVERRIDE_TYPES.update(
    _schema(
        "reference_fasta gtf_anno cram_reference STARgenome FusionGenome "
        "RNAseQC_GTF_stranded RNAseQC_GTF_unstranded kallisto_idx RSEMgenome "
        "fusion_annotator_ref hla_rna_ref_seqs hla_rna_gene_coords",
        "file",
    )
)
OVERRIDE_TYPES.update(
    _schema(
        "output_basename r1_adapter r2_adapter star_fusion_genome_untar_path "
        "outSAMattributes alignSJstitchMismatchNmax sample_name "
        "reference_profile",
        "string",
    )
)
OVERRIDE_TYPES.update(
    _schema("input_pe_rg_strs input_se_rg_strs", "string_list")
)
OVERRIDE_TYPES.update(
    _schema(
        "input_alignment_files input_pe_reads input_pe_mates input_se_reads",
        "file_list",
    )
)
OVERRIDE_TYPES.update(_schema("quality_cutoff", "int_list"))
OVERRIDE_TYPES.update(
    _schema(
        "is_paired_end run_fusions compress_chimeric_junction estimate_rspd "
        "run_rmats rmats_variable_read_length rmats_individual_counts "
        "rmats_novel_splice_sites rmats_stat_off rmats_allow_clipping run_t1k "
        "t1k_abnormal_unmap_flag",
        "bool",
    )
)
OVERRIDE_TYPES.update(
    _schema(
        "min_len quality_base read_length_median bam_strandness_nreads "
        "samtools_fastq_cores runThreadN alignSJoverhangMin limitSjdbInsertNsj "
        "chimMainSegmentMultNmax alignIntronMax alignMatesGapMax "
        "alignSJDBoverhangMin outFilterMismatchNmax alignSplicedMateMapLmin "
        "chimJunctionOverhangMin chimMultimapNmax chimMultimapScoreRange "
        "chimNonchimScoreDropMin chimOutJunctionFormat chimScoreDropMax "
        "chimScoreJunctionNonGTAG chimScoreSeparation chimSegmentMin "
        "chimSegmentReadGapMax outFilterMultimapNmax peOverlapNbasesMin "
        "arriba_memory annofuse_col_num rmats_threads rmats_ram t1k_ram",
        "int",
    )
)
OVERRIDE_TYPES.update(
    _schema(
        "read_length_stddev outFilterMismatchNoverLmax "
        "outFilterScoreMinOverLread outFilterMatchNminOverLread "
        "alignSplicedMateMapLminOverLmate peOverlapMMp",
        "float",
    )
)

ENUM_VALUES = {
    "wf_strand_param": ALLOWED_STRANDNESS,
    "twopassMode": {"Basic", "None"},
    "outFilterType": {"BySJout", "Normal"},
    "outReadsUnmapped": {"None", "Fastx"},
    "outSAMstrandField": {"intronMotif", "None"},
    "outFilterIntronMotifs": {
        "None",
        "RemoveNoncanonical",
        "RemoveNoncanonicalUnannotated",
    },
    "alignSoftClipAtReferenceEnds": {"Yes", "No"},
    "quantMode": {
        "TranscriptomeSAM GeneCounts",
        "-",
        "TranscriptomeSAM",
        "GeneCounts",
    },
    "outSAMtype": {
        "BAM Unsorted",
        "None",
        "BAM SortedByCoordinate",
        "SAM Unsorted",
        "SAM SortedByCoordinate",
    },
    "outSAMunmapped": {"Within", "None", "Within KeepPairs"},
    "genomeLoad": {
        "NoSharedMemory",
        "LoadAndKeep",
        "LoadAndRemove",
        "LoadAndExit",
    },
    "alignInsertionFlush": {"None", "Right"},
    "chimOutType": {
        "Junctions SeparateSAMold WithinBAM SoftClip",
        "Junctions",
        "SeparateSAMold",
        "WithinBAM SoftClip",
        "WithinBAM HardClip",
        "Junctions SeparateSAMold",
        "Junctions WithinBAM SoftClip",
        "Junctions WithinBAM HardClip",
        "Junctions SeparateSAMold WithinBAM HardClip",
        "SeparateSAMold WithinBAM SoftClip",
        "SeparateSAMold WithinBAM HardClip",
    },
}
OVERRIDE_TYPES.update(_schema(" ".join(ENUM_VALUES), "enum"))


CURRENT_CNH_PROFILE = VersionProfile(
    app_base="cavatica/apps-publisher/kfdrc-rnaseq-workflow",
    allowed_overrides=OVERRIDE_TYPES,
    # This is the only approved offline profile initially.  Additional profiles
    # must contain a reviewed, complete reference bundle before being added.
    reference_profiles=frozenset({"human-grch38-gencode39-v1"}),
)
VERSION_PROFILES = (CURRENT_CNH_PROFILE,)


def load_config(
    path: str | Path,
) -> tuple[dict[str, Any] | None, list[Finding]]:
    source = str(path)
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [Finding("error", "invalid-json", str(exc), source=source)]
    if not isinstance(value, dict):
        return None, [
            Finding(
                "error",
                "config-not-object",
                "Top-level JSON value must be an object.",
                source=source,
            )
        ]
    return value, []


def profile_for_app(app: str) -> VersionProfile | None:
    parts = app.strip("/").split("/")
    base = "/".join(parts[:3])
    return next(
        (profile for profile in VERSION_PROFILES if profile.app_base == base),
        None,
    )


def _valid_override_value(value: Any, value_type: str) -> bool:
    """Check JSON value shape for the corresponding CWL input type."""
    if value_type in {"string", "file"}:
        return isinstance(value, str) and bool(value.strip())
    if value_type == "bool":
        return type(value) is bool
    if value_type == "int":
        return type(value) is int
    if value_type == "float":
        return type(value) in {int, float}
    if value_type == "enum":
        return isinstance(value, str) and bool(value.strip())
    if value_type in {"string_list", "file_list"}:
        return isinstance(value, list) and all(
            isinstance(item, str) and bool(item.strip()) for item in value
        )
    if value_type == "int_list":
        return isinstance(value, list) and all(
            type(item) is int for item in value
        )
    if value_type == "float_list":
        return isinstance(value, list) and all(
            type(item) in {int, float} for item in value
        )
    if value_type == "bool_list":
        return isinstance(value, list) and all(
            type(item) is bool for item in value
        )
    raise ValueError(f"Unknown schema value type: {value_type}")


def parse_revision_notes(notes: Any) -> tuple[str | None, str | None]:
    """Return the source repository and commit from app revision notes."""
    if not isinstance(notes, str):
        return None, None
    values: dict[str, str] = {}
    for line in notes.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() in {"repo", "commit"}:
            values[key.strip().lower()] = value.strip()
    return values.get("repo"), values.get("commit")


def repository_matches(value: str | None) -> bool:
    """Accept the repository's common slug, URL, and .git URL spellings."""
    if not value:
        return False
    normalized = value.strip().lower().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized in {
        WORKFLOW_REPOSITORY,
        f"https://github.com/{WORKFLOW_REPOSITORY}",
        f"git@github.com:{WORKFLOW_REPOSITORY}",
    }


def app_commit_matches_master(
    app_commit: str | None,
    master_commit: str | None,
) -> bool:
    """Compare a GitHub master SHA with a full or abbreviated app SHA."""
    if not app_commit or not master_commit:
        return False
    app_commit = app_commit.strip().lower()
    master_commit = master_commit.strip().lower()
    return bool(re.fullmatch(r"[0-9a-f]{7,40}", app_commit)) and (
        master_commit.startswith(app_commit)
    )


def fetch_cavatica_app(
    app_id: str,
    profile: str,
    source: str = "config",
) -> tuple[dict[str, Any] | None, list[Finding]]:
    """Retrieve one app revision through the authenticated CAVATICA API."""
    try:
        import requests
    except ImportError:
        return None, [
            Finding(
                "error",
                "requests-dependency-missing",
                "Install requirements.txt for CAVATICA app validation.",
                source=source,
            )
        ]
    credentials = configparser.ConfigParser()
    credentials.read(Path.home() / ".sevenbridges" / "credentials")
    if profile not in credentials:
        return None, [
            Finding(
                "error",
                "cavatica-profile-missing",
                f"CAVATICA credentials profile {profile!r} was not found.",
                source=source,
            )
        ]
    endpoint = credentials[profile].get("api_endpoint", "").rstrip("/")
    token = credentials[profile].get("auth_token", "")
    if not endpoint or not token:
        return None, [
            Finding(
                "error",
                "cavatica-credentials-missing",
                f"CAVATICA profile {profile!r} needs api_endpoint and "
                "auth_token.",
                source=source,
            )
        ]
    try:
        response = requests.get(
            f"{endpoint}/apps/{app_id}",
            headers={"X-SBG-Auth-Token": token, "accept": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, [
            Finding(
                "error",
                "cavatica-app-request-failed",
                f"Could not retrieve CAVATICA app: {exc}",
                source=source,
            )
        ]
    if response.status_code != 200:
        return None, [
            Finding(
                "error",
                "cavatica-app-unavailable",
                f"CAVATICA app request returned HTTP {response.status_code}.",
                source=source,
            )
        ]
    try:
        payload = response.json()
    except ValueError:
        return None, [
            Finding(
                "error",
                "cavatica-app-invalid-response",
                "CAVATICA app response was not valid JSON.",
                source=source,
            )
        ]
    return payload, []


def _array_value_type(value_type: str) -> str | None:
    array_types = {
        "file": "file_list",
        "string": "string_list",
        "int": "int_list",
        "float": "float_list",
        "bool": "bool_list",
    }
    return array_types.get(value_type)


def _cwl_value_type(cwl_type: Any) -> tuple[str | None, set[str] | None]:
    """Translate a CAVATICA raw-input CWL type into a JSON value type."""
    if isinstance(cwl_type, str):
        normalized = cwl_type.rstrip("?")
        if normalized.endswith("[]"):
            item_type, _ = _cwl_value_type(normalized[:-2])
            return _array_value_type(item_type or ""), None
        aliases = {
            "File": "file",
            "string": "string",
            "int": "int",
            "float": "float",
            "boolean": "bool",
        }
        return aliases.get(normalized), None
    if isinstance(cwl_type, dict):
        if cwl_type.get("type") == "enum":
            symbols = cwl_type.get("symbols")
            if isinstance(symbols, list) and all(
                isinstance(symbol, str) for symbol in symbols
            ):
                return "enum", set(symbols)
            return None, None
        if cwl_type.get("type") == "array":
            item_type, _ = _cwl_value_type(cwl_type.get("items"))
            return _array_value_type(item_type or ""), None
        return _cwl_value_type(cwl_type.get("type"))
    if isinstance(cwl_type, list):
        members = [member for member in cwl_type if member != "null"]
        if len(members) == 1:
            return _cwl_value_type(members[0])
    return None, None


def cavatica_input_schema(
    payload: dict[str, Any],
    source: str = "config",
) -> tuple[dict[str, str], dict[str, set[str]], list[Finding]]:
    """Extract supported parameter names, types, and enum values from an app."""
    raw_inputs = payload.get("raw", {}).get("inputs")
    if not isinstance(raw_inputs, list):
        return {}, {}, [
            Finding(
                "error",
                "cavatica-app-inputs-missing",
                "CAVATICA app response has no raw.inputs list.",
                source=source,
            )
        ]
    input_types: dict[str, str] = {}
    enum_values: dict[str, set[str]] = {}
    findings: list[Finding] = []
    for item in raw_inputs:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            findings.append(
                Finding(
                    "error",
                    "cavatica-app-input-invalid",
                    "CAVATICA app has an input without a string id.",
                    source=source,
                )
            )
            continue
        input_id = item["id"]
        value_type, symbols = _cwl_value_type(item.get("type"))
        if value_type is None:
            findings.append(
                Finding(
                    "error",
                    "cavatica-app-input-type-unsupported",
                    f"App input {input_id!r} has unsupported type "
                    f"{item.get('type')!r}.",
                    source=source,
                )
            )
            continue
        input_types[input_id] = value_type
        if symbols is not None:
            enum_values[input_id] = symbols
    return input_types, enum_values, findings


def validate_app_commit(
    app_id: str,
    profile: str,
    source: str = "config",
) -> list[Finding]:
    """Compare a CAVATICA app's recorded source SHA with GitHub master.

    This is an authenticated preflight. It does not create, modify, or launch
    a CAVATICA resource.
    """
    try:
        import requests
    except ImportError:
        return [
            Finding(
                "error",
                "requests-dependency-missing",
                "Install requirements.txt to use --check-app-commit.",
                source=source,
            )
        ]
    credentials = configparser.ConfigParser()
    credentials.read(Path.home() / ".sevenbridges" / "credentials")
    if profile not in credentials:
        return [
            Finding(
                "error",
                "cavatica-profile-missing",
                f"CAVATICA credentials profile {profile!r} was not found.",
                source=source,
            )
        ]
    endpoint = credentials[profile].get("api_endpoint", "").rstrip("/")
    token = credentials[profile].get("auth_token", "")
    if not endpoint or not token:
        return [
            Finding(
                "error",
                "cavatica-credentials-missing",
                f"CAVATICA profile {profile!r} needs api_endpoint and "
                "auth_token.",
                source=source,
            )
        ]

    headers = {"X-SBG-Auth-Token": token, "accept": "application/json"}
    try:
        response = requests.get(
            f"{endpoint}/apps/{app_id}",
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        return [
            Finding(
                "error",
                "cavatica-app-request-failed",
                f"Could not retrieve CAVATICA app: {exc}",
                source=source,
            )
        ]
    if response.status_code != 200:
        return [
            Finding(
                "error",
                "cavatica-app-unavailable",
                f"CAVATICA app request returned HTTP {response.status_code}.",
                source=source,
            )
        ]
    try:
        payload = response.json()
    except ValueError:
        return [
            Finding(
                "error",
                "cavatica-app-invalid-response",
                "CAVATICA app response was not valid JSON.",
                source=source,
            )
        ]
    notes = payload.get("raw", {}).get("sbg:revisionNotes")
    repository, app_commit = parse_revision_notes(notes)
    if not repository_matches(repository):
        return [
            Finding(
                "error",
                "app-repository-mismatch",
                "App revision notes must identify "
                f"{WORKFLOW_REPOSITORY!r}; found {repository!r}.",
                source=source,
            )
        ]

    try:
        response = requests.get(
            GITHUB_MASTER_COMMIT_URL,
            headers={"accept": "application/vnd.github+json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return [
            Finding(
                "error",
                "github-master-request-failed",
                f"Could not retrieve GitHub master commit: {exc}",
                source=source,
            )
        ]
    if response.status_code != 200:
        return [
            Finding(
                "error",
                "github-master-unavailable",
                "GitHub master-commit request returned "
                f"HTTP {response.status_code}.",
                source=source,
            )
        ]
    try:
        master_commit = response.json().get("sha")
    except ValueError:
        master_commit = None
    if not app_commit_matches_master(app_commit, master_commit):
        return [
            Finding(
                "error",
                "app-commit-mismatch",
                "CAVATICA app commit "
                f"{app_commit!r} does not match GitHub master "
                f"{master_commit!r}.",
                source=source,
            )
        ]
    return [
        Finding(
            "info",
            "app-commit-match",
            f"CAVATICA app commit {app_commit} matches GitHub master.",
            source=source,
        )
    ]


def validate_config(
    config: dict[str, Any],
    source: str = "config",
    app_input_types: dict[str, str] | None = None,
    app_enum_values: dict[str, set[str]] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    # Workflow inputs are flattened alongside project and app in the config.
    # This makes the review artifact match the options-file input names.
    workflow_types = (
        OVERRIDE_TYPES if app_input_types is None else app_input_types
    )
    workflow_enums = (
        ENUM_VALUES if app_enum_values is None else app_enum_values
    )
    allowed_keys = {"project", "app"} | set(CONFIG_METADATA_TYPES)
    allowed_keys |= set(workflow_types)
    for key in sorted(set(config) - allowed_keys):
        findings.append(
            Finding(
                "error",
                "unknown-config-key",
                f"Unsupported key {key!r}.",
                source=source,
            )
        )

    project = config.get("project")
    app = config.get("app")
    if not isinstance(project, str) or not project.strip():
        findings.append(
            Finding(
                "error",
                "project-required",
                "project must be a nonempty string.",
                source=source,
            )
        )
    elif "REPLACE_WITH" in project:
        findings.append(
            Finding(
                "error",
                "project-placeholder",
                "Replace the example project placeholder with a real "
                "CAVATICA project ID.",
                source=source,
            )
        )
    elif not PROJECT_ID_RE.fullmatch(project):
        findings.append(
            Finding(
                "error",
                "project-format",
                "project must have owner/project form.",
                source=source,
            )
        )
    if not isinstance(app, str) or not app.strip():
        findings.append(
            Finding(
                "error",
                "app-required",
                "app must be a nonempty string.",
                source=source,
            )
        )
        return findings
    if not APP_ID_RE.fullmatch(app):
        findings.append(
            Finding(
                "error",
                "app-format",
                "app must have owner/project/app form with optional /revision.",
                source=source,
            )
        )
        return findings

    profile = profile_for_app(app)
    if profile is None and app_input_types is None:
        findings.append(
            Finding(
                "error",
                "unknown-app-version",
                "No validation profile exists for this app; add a reviewed "
                "version profile.",
                source=source,
            )
        )
        return findings

    for key, value in config.items():
        if key in {"project", "app"}:
            continue
        if key in CONFIG_METADATA_TYPES:
            expected = CONFIG_METADATA_TYPES[key]
            if not _valid_override_value(value, expected):
                findings.append(
                    Finding(
                        "error",
                        "metadata-type",
                        f"{key!r} must be a valid {expected} value.",
                        source=source,
                    )
                )
            elif key in CONFIG_METADATA_ENUMS and (
                value not in CONFIG_METADATA_ENUMS[key]
            ):
                findings.append(
                    Finding(
                        "error",
                        "metadata-value",
                        f"{key!r} must be one of: "
                        f"{', '.join(sorted(CONFIG_METADATA_ENUMS[key]))}.",
                        source=source,
                    )
                )
            continue
        expected = workflow_types.get(key)
        if expected is None:
            findings.append(
                Finding(
                    "error",
                    "unknown-override",
                    f"{key!r} is not supported by this app profile.",
                    source=source,
                )
            )
            continue
        if not _valid_override_value(value, expected):
            findings.append(
                Finding(
                    "error",
                    "override-type",
                    f"{key!r} must be a valid {expected} value.",
                    source=source,
                )
            )
            continue
        if (
            profile is not None
            and key == "reference_profile"
            and value not in profile.reference_profiles
        ):
            findings.append(
                Finding(
                    "error",
                    "unknown-reference-profile",
                    f"{value!r} is not a reviewed reference profile for this "
                    "app.",
                    source=source,
                )
            )
        elif key in workflow_enums and value not in workflow_enums[key]:
            findings.append(
                Finding(
                    "error",
                    "enum-value",
                    f"{key!r} must be one of: "
                    f"{', '.join(sorted(workflow_enums[key]))}.",
                    source=source,
                )
            )
        elif key in {"r1_adapter", "r2_adapter"} and not ADAPTER_RE.fullmatch(
            value
        ):
            findings.append(
                Finding(
                    "error",
                    "adapter-sequence",
                    f"{key!r} must contain only A, C, G, T, or N.",
                    source=source,
                )
            )
        elif key in {
            "min_len",
            "quality_base",
            "samtools_fastq_cores",
            "runThreadN",
            "outFilterMultimapNmax",
            "arriba_memory",
        } and value <= 0:
            findings.append(
                Finding(
                    "error",
                    "positive-integer",
                    f"{key} must be greater than zero.",
                    source=source,
                )
            )
        else:
            findings.append(
                Finding(
                    "warning",
                    "default-override",
                    f"{key!r} overrides an app default or generated value; "
                    "review it explicitly.",
                    source=source,
                )
            )
    return findings


def _truthy(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _input_mode(row: dict[str, str]) -> str | None:
    value = row.get("file_format", "").strip().upper()
    name = row.get("file_name", "").strip().lower()
    fastq_extensions = (".fastq", ".fastq.gz", ".fq", ".fq.gz")
    if value in {"FASTQ", "FASTQ.GZ", "FQ", "FQ.GZ"} or name.endswith(
        fastq_extensions
    ):
        return "fastq"
    if value == "BAM" or name.endswith(".bam"):
        return "bam"
    if value == "CRAM" or name.endswith(".cram"):
        return "cram"
    return None


def _read_stem(name: str, read_number: str) -> str | None:
    """Return a conservative shared stem for standard R1/R2 filename styles."""
    base = re.sub(r"\.(?:fastq|fq)(?:\.gz)?$", "", name, flags=re.IGNORECASE)
    patterns = (
        (r"([._-])R([12])([._-]|$)", r"\1R{read}\3"),
        (r"([._-])([12])$", r"\1{read}"),
    )
    for pattern, replacement in patterns:
        match = re.search(pattern, base, flags=re.IGNORECASE)
        if match and match.group(2) == read_number:
            return re.sub(
                pattern,
                replacement.format(read="N"),
                base,
                count=1,
                flags=re.IGNORECASE,
            )
    return None


def read_manifest(
    path: str | Path,
) -> tuple[list[dict[str, str]], list[Finding]]:
    source = str(path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            columns = set(reader.fieldnames or [])
            missing = REQUIRED_MANIFEST_COLUMNS - columns
            findings = [
                Finding(
                    "error",
                    "missing-manifest-column",
                    f"Required column {column!r} is absent.",
                    source=source,
                )
                for column in sorted(missing)
            ]
            if not (columns & ORGANISM_COLUMNS):
                findings.append(
                    Finding(
                        "error",
                        "missing-organism-column",
                        "Require organism or host_organism column.",
                        source=source,
                    )
                )
            if findings:
                return [], findings
            return list(reader), []
    except OSError as exc:
        return [], [
            Finding("error", "manifest-read-error", str(exc), source=source)
        ]


def validate_manifest(
    rows: Iterable[dict[str, str]],
    source: str = "manifest",
    config: dict[str, Any] | None = None,
) -> list[Finding]:
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    findings: list[Finding] = []
    for row_number, row in enumerate(rows, start=2):
        bioassay_id = row.get("Bioassay_ID", "").strip()
        if not bioassay_id:
            findings.append(
                Finding(
                    "error",
                    "bioassay-required",
                    "Bioassay_ID must be nonempty.",
                    source,
                    row_number,
                )
            )
            continue
        if not row.get("file_name", "").strip():
            findings.append(
                Finding(
                    "error",
                    "file-name-required",
                    "file_name must be nonempty.",
                    source,
                    row_number,
                    bioassay_id,
                )
            )
        grouped[bioassay_id].append((row_number, row))

    config_values = config or {}
    for bioassay_id, entries in grouped.items():
        modes = {_input_mode(row) for _, row in entries}
        if None in modes:
            for row_number, row in entries:
                if _input_mode(row) is None:
                    message = (
                        "Unsupported file_format/file_name: "
                        f"{row.get('file_format', '')!r}/"
                        f"{row.get('file_name', '')!r}."
                    )
                    findings.append(
                        Finding(
                            "error",
                            "unsupported-file-type",
                            message,
                            source,
                            row_number,
                            bioassay_id,
                        )
                    )
            continue
        if len(modes) != 1:
            findings.append(
                Finding(
                    "error",
                    "mixed-input-modes",
                    "A task may contain only FASTQ, BAM, or CRAM inputs, "
                    "not a mixture.",
                    source,
                    bioassay_id=bioassay_id,
                )
            )
            continue
        mode = modes.pop()
        if mode == "fastq":
            paired_values = {
                _truthy(row.get("is_paired_end", "")) for _, row in entries
            }
            if None in paired_values or len(paired_values) != 1:
                findings.append(
                    Finding(
                        "error",
                        "paired-end-value",
                        "is_paired_end must be a consistent TRUE/FALSE value "
                        "for this task.",
                        source,
                        bioassay_id=bioassay_id,
                    )
                )
                continue
            if paired_values.pop():
                r1 = [
                    (number, row)
                    for number, row in entries
                    if row.get("read_pair_number", "").strip().upper() == "R1"
                ]
                r2 = [
                    (number, row)
                    for number, row in entries
                    if row.get("read_pair_number", "").strip().upper() == "R2"
                ]
                if len(r1) != len(r2) or not r1:
                    findings.append(
                        Finding(
                            "error",
                            "unpaired-fastq",
                            "Paired FASTQ requires equal nonzero R1 and R2 "
                            "counts.",
                            source,
                            bioassay_id=bioassay_id,
                        )
                    )
                    continue
                r1_stems = sorted(
                    _read_stem(row["file_name"], "1") for _, row in r1
                )
                r2_stems = sorted(
                    _read_stem(row["file_name"], "2") for _, row in r2
                )
                if None in r1_stems or None in r2_stems or r1_stems != r2_stems:
                    findings.append(
                        Finding(
                            "error",
                            "pair-name-mismatch",
                            "R1/R2 filenames do not form unambiguous matching "
                            "read pairs.",
                            source,
                            bioassay_id=bioassay_id,
                        )
                    )
            elif any(
                row.get("read_pair_number", "").strip() for _, row in entries
            ):
                findings.append(
                    Finding(
                        "error",
                        "single-end-pair-label",
                        "Single-end FASTQ must not have R1/R2 labels.",
                        source,
                        bioassay_id=bioassay_id,
                    )
                )
        elif mode == "cram" and "cram_reference" not in config_values:
            findings.append(
                Finding(
                    "error",
                    "cram-reference-required",
                    "CRAM input requires an approved cram_reference value "
                    "with its .fai file.",
                    source,
                    bioassay_id=bioassay_id,
                )
            )
    if not grouped:
        findings.append(
            Finding(
                "error",
                "no-input-records",
                "Manifest has no usable records.",
                source,
            )
        )
    return findings


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(finding.severity == "error" for finding in findings)
