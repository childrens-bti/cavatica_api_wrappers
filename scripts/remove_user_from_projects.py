"""Remove a user from a single project or projects owned by selected accounts."""

import click
from sevenbridges.errors import Forbidden
from helper_functions import helper_functions as hf
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
REFERENCE_PROJECT = "childrens-bti/childrens-bti-references"


def find_member_username(project, user):
    """Read every member page and return the matching username, if present."""
    members = project.get_members(limit=hf.LIMIT)
    usernames = {member.username for member in members}
    offset = hf.LIMIT
    while offset < members.total:
        members = project.get_members(limit=hf.LIMIT, offset=offset)
        usernames.update(member.username for member in members)
        offset += hf.LIMIT
    return next((name for name in usernames if name.casefold() == user.casefold()), None)


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
@click.option("--user", help="Username to remove from projects", required=True)
@click.option("--project", help="Project ID or URL to remove the user from")
@click.option(
    "--project_creator",
    help=(
        "Comma-separated project owners (username or organization prefix in the "
        "project ID), regardless of who created the project"
    ),
)
def remove_user(profile, user, project, project_creator):
    """Remove a user from the selected projects.

    childrens-bti/childrens-bti-references is protected: explicit selection is
    rejected, and bulk selection reports it as skipped.
    """
    if project is not None and project_creator is not None:
        raise click.UsageError("--project and --project_creator are mutually exclusive")
    if project is None and project_creator is None:
        raise click.UsageError("Provide either --project or --project_creator")

    user = user.strip()
    if not user:
        raise click.BadParameter("Username must not be empty", param_hint="--user")

    owners = set()
    if project_creator is not None:
        for owner in project_creator.split(","):
            owner = owner.strip()
            if not owner:
                raise click.BadParameter(
                    "Provide comma-separated owners without empty entries",
                    param_hint="--project_creator",
                )
            owners.add(owner)

    if project is not None:
        try:
            project = hf.parse_project(project.strip())
            if any(not part.strip() for part in project.split("/")):
                raise ValueError("Empty owner or project name")
        except (ValueError, IndexError):
            raise click.BadParameter(
                "Provide owner/project or a URL containing /u/owner/project",
                param_hint="--project",
            ) from None
        if project == REFERENCE_PROJECT:
            raise click.UsageError(
                f"Cannot remove users from protected reference project {REFERENCE_PROJECT}"
            )

    # read config file
    api = hf.parse_config(profile)
    current_user = api.users.me()
    if user.casefold() == current_user.username.casefold():
        raise click.ClickException(
            f"Cannot remove the authenticated user {current_user.username} from projects"
        )

    if project is not None:
        projs = [api.projects.get(id=project)]
    else:
        projs = hf.get_all_projects(api, strict=True)

    unmatched_owners = owners.copy()
    eligible_count = 0
    outcomes = {
        "Removed": [],
        "Already absent": [],
        "Failed to verify or remove": [],
        "Outcome unconfirmed": [],
        "Not processed": [],
        "Protected/skipped": [],
    }
    pending_error = None
    eligible_projects = []
    try:
        with tqdm(projs, desc="Removing user from projects", unit="project") as progress:
            for p in progress:
                owner = p.id.split("/")[0]
                if project is None and owner not in owners:
                    continue
                unmatched_owners.discard(owner)
                if p.id == REFERENCE_PROJECT:
                    outcomes["Protected/skipped"].append(p.id)
                    continue
                eligible_count += 1
                eligible_projects.append(p)
                if pending_error is not None:
                    outcomes["Not processed"].append(p.id)
                    continue
                removal_started = False
                try:
                    member = find_member_username(p, user)
                    if member is not None:
                        removal_started = True
                        p.remove_member(user=member)
                        outcomes["Removed"].append(p.id)
                    else:
                        outcomes["Already absent"].append(p.id)
                except Forbidden:
                    outcomes["Failed to verify or remove"].append(p.id)
                    tqdm.write(f"Insufficient permissions for {p.id}; skipping")
                except BaseException as error:
                    # An error does not guarantee the user still has access.
                    # The SDK handles retries; do not add another retry here.
                    status = (
                        "Outcome unconfirmed" if removal_started
                        else "Failed to verify or remove"
                    )
                    outcomes[status].append(p.id)
                    # Stop further removals, but ordinary errors can still be
                    # resolved by the final membership check.
                    pending_error = error

        # Respect interruptions immediately; otherwise check the actual state
        # of every eligible project, including failed or unprocessed removals.
        if pending_error is None or isinstance(pending_error, Exception):
            remaining = eligible_projects
            confirmed_absent = []
            for attempt in range(1, 6):
                outcomes = {
                    "Confirmed absent": confirmed_absent,
                    "Still has access": [],
                    "Could not verify": [p.id for p in remaining],
                    "Protected/skipped": outcomes["Protected/skipped"],
                }
                if attempt > 1:
                    click.echo(f"Attempt {attempt}/5: retrying {len(remaining)} unresolved project(s)")
                    for p in tqdm(remaining, desc="Retrying removals", unit="project"):
                        try:
                            member = find_member_username(p, user)
                            if member is not None:
                                p.remove_member(user=member)
                        except Exception as error:
                            tqdm.write(f"Could not remove user from {p.id}: {error}")

                for p in tqdm(remaining, desc="Verifying membership", unit="project"):
                    try:
                        member = find_member_username(p, user)
                    except Exception as error:
                        tqdm.write(f"Could not verify membership in {p.id}: {error}")
                        continue
                    status = "Still has access" if member is not None else "Confirmed absent"
                    outcomes[status].append(p.id)
                    outcomes["Could not verify"].remove(p.id)

                if len(confirmed_absent) == eligible_count:
                    break
                confirmed_ids = set(confirmed_absent)
                remaining = [p for p in eligible_projects if p.id not in confirmed_ids]
    finally:
        for owner in sorted(unmatched_owners):
            click.echo(f"Warning: no projects matched owner {owner}")
        report_outcomes(user, eligible_count, outcomes)

    if pending_error is not None and not isinstance(pending_error, Exception):
        raise pending_error

    errors = []
    if unmatched_owners:
        errors.append(f"No projects matched owners: {', '.join(sorted(unmatched_owners))}")
    if outcomes["Still has access"]:
        errors.append(
            f"User {user} still has access to projects: {', '.join(outcomes['Still has access'])}"
        )
    if outcomes["Could not verify"]:
        errors.append(
            f"Could not verify membership for user {user} in projects: "
            f"{', '.join(outcomes['Could not verify'])}"
        )
    if errors:
        raise click.ClickException("; ".join(errors))

    print("Finished removing user from projects")


if __name__ == "__main__":
    remove_user()
