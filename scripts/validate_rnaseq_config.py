#!/usr/bin/env python3
"""Validate a minimal RNA-seq config, optionally with its manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from rnaseq_config import (
    cavatica_input_schema,
    fetch_cavatica_app,
    has_errors,
    load_config,
    read_manifest,
    validate_app_payload_version,
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
    parser.add_argument(
        "--check-app-version",
        action="store_true",
        help=(
            "Use CAVATICA credentials to require RNA-seq workflow version "
            "v1.2.4 in the selected app's revision notes"
        ),
    )
    parser.add_argument(
        "--check-cavatica-app",
        action="store_true",
        help=(
            "Use the selected CAVATICA app revision's live input schema "
            "after confirming it uses RNA-seq workflow version v1.2.4"
        ),
    )
    parser.add_argument(
        "--profile",
        default="turbo",
        help="CAVATICA credentials profile for app checks",
    )
    args = parser.parse_args()

    config, findings = load_config(args.config)
    if config is not None:
        app_id = config.get("app")
        app_payload = None
        version_findings = []
        if (
            (args.check_cavatica_app or args.check_app_version)
            and isinstance(app_id, str)
        ):
            app_payload, app_findings = fetch_cavatica_app(
                app_id,
                args.profile,
                str(args.config),
            )
            findings.extend(app_findings)
            if app_payload is not None:
                version_findings = validate_app_payload_version(
                    app_payload,
                    str(args.config),
                )
                findings.extend(version_findings)
        if args.check_cavatica_app:
            if app_payload is not None and not has_errors(version_findings):
                (
                    input_types,
                    enum_values,
                    schema_findings,
                ) = cavatica_input_schema(app_payload, str(args.config))
                findings.extend(schema_findings)
                findings.extend(
                    validate_config(
                        config,
                        str(args.config),
                        input_types,
                        enum_values,
                    )
                )
        else:
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
