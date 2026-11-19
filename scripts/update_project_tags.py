"""Add tags to Cavatica projects from a TSV file."""

import csv

import click
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option(
    "--tag_file",
    help="TSV file with project IDs or URLs and comma-separated tags in project and tag columns",
    required=True,
)
@click.option("--verbose", help="Print tags added to each project", is_flag=True)
def update_project_tags(profile, tag_file, verbose):
    """Add the tags in each file row to its project."""
    api = hf.parse_config(profile)
    project_count = 0
    with open(tag_file, newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tags = [tag.strip() for tag in row["tag"].split(",") if tag.strip()]
            if not tags:
                print(f"Warning: no tags for project {row['project']}; skipping")
                continue
            project_id = hf.parse_project(row["project"].strip())
            project = api.projects.get(project_id)
            project.tags = list(project.tags or []) + tags
            project.save()
            project_count += 1
            if verbose:
                print(f"Added tags to {project.id}: {', '.join(tags)}")

    print(f"Added tags to {project_count} projects")


if __name__ == "__main__":
    update_project_tags()
