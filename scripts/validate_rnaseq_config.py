#!/usr/bin/env python3
"""Validate a minimal RNA-seq config, optionally with its manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from rnaseq_config import (
    has_errors,
    load_config,
    read_manifest,
    validate_config,
    validate_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        type=Path,
        help="Minimal RNA-seq JSON configuration",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Reviewed RNA-seq manifest TSV to group into tasks",
    )
    args = parser.parse_args()

    config, findings = load_config(args.config)
    if config is not None:
        findings.extend(validate_config(config, str(args.config)))
    if args.manifest and config is not None:
        rows, manifest_findings = read_manifest(args.manifest)
        findings.extend(manifest_findings)
        if not has_errors(manifest_findings):
            findings.extend(validate_manifest(rows, str(args.manifest), config))
    for finding in findings:
        print(finding.format())
    if has_errors(findings):
        print("Validation failed.")
        return 1
    message = "Validation passed."
    if findings:
        message += " Warnings require review."
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
