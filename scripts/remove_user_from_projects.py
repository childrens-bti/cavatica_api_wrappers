"""Remove a user from a single project or projects owned by selected creators."""

import click
from sevenbridges.errors import Forbidden
from helper_functions import helper_functions as hf
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--user", help="Username to check for in projects", required=True)
@click.option("--project", help="Project ID or URL to remove the user from")
@click.option(
    "--project_creator",
    help="Username(s) of project creator to check for",
)
def remove_user(profile, user, project, project_creator):
    """Remove a user from the selected projects."""
    if project is not None and project_creator is not None:
        raise click.UsageError("--project and --project_creator are mutually exclusive")
    if project is None and project_creator is None:
        raise click.UsageError("Provide either --project or --project_creator")

    # read config file
    api = hf.parse_config(profile)

    if project is not None:
        projs = [api.projects.get(id=hf.parse_project(project))]
    else:
        pcs = set(project_creator.split(","))
        projs = hf.get_all_projects(api)

    for p in tqdm(projs, desc="Removing user from projects", unit="project"):
        if p.id == "childrens-bti/childrens-bti-references":
            continue
        if project is None and p.id.split("/")[0] not in pcs:
            continue
        try:
            users = p.get_members()
            usernames = {member.username for member in users}
            if user in usernames:
                p.remove_member(
                    user=user,
                )
        except Forbidden:
            tqdm.write(f"Insufficient permissions for {p.id}; skipping")

    print("Finished removing user from projects")


if __name__ == "__main__":
    remove_user()
