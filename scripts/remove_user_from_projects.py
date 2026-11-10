"""Remove a user from a single project or projects owned by selected creators."""

import click
from sevenbridges.errors import Forbidden
from helper_functions import helper_functions as hf
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
REFERENCE_PROJECT = "childrens-bti/childrens-bti-references"


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

    if project is not None:
        project = hf.parse_project(project)
        if project == REFERENCE_PROJECT:
            raise click.UsageError(
                f"Cannot remove users from protected reference project {REFERENCE_PROJECT}"
            )

    # read config file
    api = hf.parse_config(profile)

    if project is not None:
        projs = [api.projects.get(id=project)]
    else:
        pcs = set(project_creator.split(","))
        projs = hf.get_all_projects(api, strict=True)

    failed_projects = []
    for p in tqdm(projs, desc="Removing user from projects", unit="project"):
        if p.id == REFERENCE_PROJECT:
            continue
        if project is None and p.id.split("/")[0] not in pcs:
            continue
        try:
            users = p.get_members(limit=hf.LIMIT)
            usernames = {member.username for member in users}
            offset = hf.LIMIT
            while offset < users.total:
                users = p.get_members(limit=hf.LIMIT, offset=offset)
                usernames.update(member.username for member in users)
                offset += hf.LIMIT
            if user in usernames:
                p.remove_member(
                    user=user,
                )
        except Forbidden:
            failed_projects.append(p.id)
            tqdm.write(f"Insufficient permissions for {p.id}; skipping")

    if failed_projects:
        raise click.ClickException(
            f"Could not verify or remove user {user} due to insufficient permissions "
            f"in projects: {', '.join(failed_projects)}"
        )

    print("Finished removing user from projects")


if __name__ == "__main__":
    remove_user()
