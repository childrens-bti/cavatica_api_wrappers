"""Validate input config file."""

import json
import click
from pathlib import Path
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def load_config(path):
    """Load a task-input JSON object without changing the caller's data."""
    try:
        with open(path, "r") as handle:
            config = json.load(handle)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(config, dict):
        raise click.ClickException("The config must contain one JSON object")
    app = config.get("app")
    if not isinstance(app, str) or not app.strip():
        raise click.ClickException("The config must contain a non-empty string app")
    return app.strip(), {key: value for key, value in config.items() if key != "app"}


def enum_values(input_definition):
    """Return enum symbols from the common CWL/API input representations."""
    input_type = input_definition.get("type")
    candidates = input_type if isinstance(input_type, list) else [input_type]
    for candidate in candidates:
        if isinstance(candidate, dict):
            symbols = candidate.get("symbols")
            if symbols is not None:
                return symbols
    symbols = input_definition.get("symbols")
    return symbols if symbols is not None else []


def input_is_required(input_definition):
    """Return whether an input's CWL type excludes null."""
    input_type = input_definition.get("type")
    types = input_type if isinstance(input_type, list) else [input_type]
    return (
        bool(types)
        and "null" not in types
        and not any(
            isinstance(candidate, dict) and candidate.get("type") == "null"
            for candidate in types
        )
    )


def input_definitions(app):
    """Map input IDs to their raw app definitions."""
    try:
        inputs = app.raw["inputs"]
    except (AttributeError, KeyError, TypeError) as exc:
        raise click.ClickException(
            "The app response did not contain raw inputs"
        ) from exc
    return {input_definition["id"]: input_definition for input_definition in inputs}


def compare_config(config, definitions):
    """Return rows and validation errors for config values and app inputs."""

    unknown = sorted(set(config) - set(definitions))
    errors = [f"unknown input: {key}" for key in unknown]
    rows = []

    for key, definition in definitions.items():
        has_value = key in config
        has_default = "default" in definition
        has_suggested = "sbg:suggestedValue" in definition
        value = config.get(key)
        fallback_name = "default" if has_default else "suggested value"
        fallback = (
            definition.get("default")
            if has_default
            else definition.get("sbg:suggestedValue")
        )
        if fallback and type(fallback) is dict and "name" in fallback:
            fallback = fallback.get("name")

        symbols = enum_values(definition)

        if symbols and has_value and value not in symbols:
            errors.append(
                f"invalid value for {key}: {value!r} (expected one of {symbols!r})"
            )

        if has_value:
            status = (
                f"matches {fallback_name}"
                if (has_default or has_suggested) and value == fallback
                else (
                    f"overrides {fallback_name}"
                    if (has_default or has_suggested)
                    else "explicit (no default or suggested value)"
                )
            )
            rows.append(
                (key, status, value, fallback if has_default or has_suggested else "-")
            )
        elif has_default or has_suggested:
            rows.append((key, f"uses {fallback_name}", "-", fallback))

    return rows, errors


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--profile",
    default="cavatica",
    show_default=True,
    help="Profile to use from the Seven Bridges credentials file.",
)
def check_app_defaults(config, profile):
    """Compare CONFIG's inputs with the defaults in its CAVATICA app."""
    app_id, task_inputs = load_config(config)

    api = hf.parse_config(profile)
    app = api.apps.get(app_id)

    # Will eventually check if app is loaded and if not grab and load the official version
    # or would it be better to fail here and launch another runner that loads it?

    definitions = input_definitions(app)
    rows, errors = compare_config(task_inputs, definitions)
    click.echo(f"App: {app_id}")
    click.echo(f"Config: {config}")
    click.echo("\nInput\tStatus\tConfig value\tApp default")
    for key, status, value, default in rows:
        click.echo(f"{key}\t{status}\t{value!r}\t{default!r}")

    if errors:
        validation = "Validation failed, incorrect inputs given"
    elif any(status.startswith(("overrides", "explicit")) for _, status, _, _ in rows):
        validation = "Validation requires inspection"
    else:
        validation = "Validation OK"
    click.echo(validation)

    if errors:
        for error in errors:
            click.echo(f"ERROR: {error}", err=True)
        raise click.exceptions.Exit(1)


if __name__ == "__main__":
    check_app_defaults()
