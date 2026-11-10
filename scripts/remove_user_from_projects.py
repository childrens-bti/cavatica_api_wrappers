"""Remove a user from a single project or projects owned by selected creators."""

import click
from sevenbridges.errors import Forbidden
from helper_functions import helper_functions as hf
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
REFERENCE_PROJECT = "childrens-bti/childrens-bti-references"


def report_outcomes(user, eligible_count, outcomes):
    """Report confirmed outcomes and any projects left unprocessed."""
    click.echo(f"Removal summary for {user}: {eligible_count} eligible project(s)")
    for status, projects in outcomes.items():
        if projects:
            click.echo(f"{status} ({len(projects)}): {', '.join(projects)}")


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

    user = user.strip()
    if not user:
        raise click.BadParameter("Username must not be empty", param_hint="--user")

    pcs = set()
    if project_creator is not None:
        for creator in project_creator.split(","):
            creator = creator.strip()
            if not creator:
                raise click.BadParameter(
                    "Provide comma-separated usernames without empty entries",
                    param_hint="--project_creator",
                )
            pcs.add(creator)

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
        projs = hf.get_all_projects(api, strict=True)

    unmatched_owners = pcs.copy()
    eligible_count = 0
    outcomes = {
        "Removed": [],
        "Already absent": [],
        "Failed to verify or remove": [],
        "Outcome unconfirmed": [],
        "Not processed": [],
    }
    pending_error = None
    try:
        with tqdm(projs, desc="Removing user from projects", unit="project") as progress:
            for p in progress:
                if p.id == REFERENCE_PROJECT:
                    continue
                owner = p.id.split("/")[0]
                if project is None and owner not in pcs:
                    continue
                unmatched_owners.discard(owner)
                eligible_count += 1
                if pending_error is not None:
                    outcomes["Not processed"].append(p.id)
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
                        p.remove_member(user=user)
                        outcomes["Removed"].append(p.id)
                    else:
                        outcomes["Already absent"].append(p.id)
                except Forbidden:
                    outcomes["Failed to verify or remove"].append(p.id)
                    tqdm.write(f"Insufficient permissions for {p.id}; skipping")
                except BaseException as error:
                    # A failed DELETE may have reached the server. Do not claim
                    # the membership is unchanged or automatically retry it.
                    status = (
                        "Failed to verify or remove"
                        if isinstance(error, Exception) else "Outcome unconfirmed"
                    )
                    outcomes[status].append(p.id)
                    # Finish local accounting in this pass without further API
                    # calls, then propagate the original error after the summary.
                    pending_error = error
    finally:
        for owner in sorted(unmatched_owners):
            click.echo(f"Warning: no eligible projects matched owner {owner}")
        report_outcomes(user, eligible_count, outcomes)

    if pending_error is not None:
        raise pending_error

    if outcomes["Failed to verify or remove"]:
        raise click.ClickException(
            f"Could not verify or remove user {user} due to insufficient permissions "
            f"in projects: {', '.join(outcomes['Failed to verify or remove'])}"
        )

    print("Finished removing user from projects")


if __name__ == "__main__":
    remove_user()
