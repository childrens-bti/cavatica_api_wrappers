"""Remove a user from a single project or projects owned by selected accounts."""

import time

import click
from sevenbridges.errors import Forbidden, SbgError
from helper_functions import helper_functions as hf
from tqdm import tqdm

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
REFERENCE_PROJECT = "childrens-bti/childrens-bti-references"


def find_member_usernames(project, user):
    """Read every member page and return all matching spellings in order."""
    members = project.get_members(limit=hf.LIMIT)
    total = members.total
    usernames = [member.username for member in members]
    for offset in range(hf.LIMIT, total, hf.LIMIT):
        members = project.get_members(limit=hf.LIMIT, offset=offset)
        if members.total != total:
            raise SbgError(message="Project membership changed during pagination")
        usernames.extend(member.username for member in members)
    if len(usernames) != total or len(set(usernames)) != total:
        raise SbgError(message="Project membership listing was incomplete or duplicated")
    target = user.casefold()
    return [name for name in usernames if name is not None and name.casefold() == target]


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
            owners.add(owner.casefold())

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

    try:
        if project is not None:
            projs = [api.projects.get(id=project)]
        else:
            projs = []
            for owner in sorted(owners):
                projs.extend(hf.get_all_projects(api, strict=True, owner=owner))
    except SbgError as error:
        raise click.ClickException(f"Could not load selected projects: {error}") from error

    unmatched_owners = owners.copy()
    eligible_projects = []
    protected = []
    seen_ids = set()
    for p in projs:
        owner = p.id.split("/")[0].casefold()
        if project is None and owner not in owners:
            continue
        unmatched_owners.discard(owner)
        if p.id in seen_ids:
            continue
        seen_ids.add(p.id)
        if p.id == REFERENCE_PROJECT:
            protected.append(p.id)
        else:
            eligible_projects.append(p)

    statuses = {p.id: "Not processed" for p in eligible_projects}
    known_members = {}
    permission_denied = set()
    unreadable = set()
    remaining = eligible_projects
    try:
        for attempt in range(1, 6):
            if not remaining:
                break
            if attempt > 1:
                delay = 5 * 2 ** (attempt - 2)
                click.echo(
                    f"Attempt {attempt}/5: retrying {len(remaining)} unresolved project(s) "
                    f"after {delay}s"
                )
                time.sleep(delay)
            verify = []
            for p in tqdm(remaining, desc="Removing user from projects", unit="project"):
                statuses[p.id] = "Failed to verify or remove"
                try:
                    # A successful verification from the previous attempt
                    # already tells us which spellings still need removal.
                    members = known_members.pop(p.id, None)
                    if members is None:
                        try:
                            members = find_member_usernames(p, user)
                        except Forbidden:
                            unreadable.add(p.id)
                            raise
                    if not members:
                        statuses[p.id] = "Already absent" if attempt == 1 else "Confirmed absent"
                    else:
                        statuses[p.id] = "Outcome unconfirmed"
                        for member in members:
                            p.remove_member(user=member)
                        statuses[p.id] = "Removed"
                except Forbidden:
                    permission_denied.add(p.id)
                    statuses[p.id] = "Could not verify" if p.id in unreadable else "Still has access"
                    tqdm.write(f"Insufficient permissions for {p.id}; no retries")
                except Exception as error:
                    tqdm.write(f"Could not verify or remove user from {p.id}: {error}")
                # Verify applied/uncertain removals and initial absences after
                # the whole removal pass. A denied read cannot be retried.
                if p.id not in unreadable and statuses[p.id] != "Confirmed absent":
                    verify.append(p)

            for p in tqdm(verify, desc="Verifying membership", unit="project"):
                statuses[p.id] = "Could not verify"
                try:
                    members = find_member_usernames(p, user)
                except Forbidden as error:
                    permission_denied.add(p.id)
                    tqdm.write(f"Could not verify membership in {p.id}: {error}; no retries")
                except Exception as error:
                    tqdm.write(f"Could not verify membership in {p.id}: {error}")
                else:
                    statuses[p.id] = "Still has access" if members else "Confirmed absent"
                    known_members[p.id] = members

            remaining = [
                p for p in eligible_projects
                if statuses[p.id] != "Confirmed absent" and p.id not in permission_denied
            ]
    finally:
        outcomes = {}
        for project_id, status in statuses.items():
            outcomes.setdefault(status, []).append(project_id)
        outcomes["Protected/skipped"] = protected
        for owner in sorted(unmatched_owners):
            click.echo(f"Warning: no projects matched owner {owner}")
        report_outcomes(user, len(eligible_projects), outcomes)

    errors = []
    if unmatched_owners:
        errors.append(f"No projects matched owners: {', '.join(sorted(unmatched_owners))}")
    if outcomes.get("Still has access"):
        errors.append(
            f"User {user} still has access to projects: {', '.join(outcomes['Still has access'])}"
        )
    if outcomes.get("Could not verify"):
        errors.append(
            f"Could not verify membership for user {user} in projects: "
            f"{', '.join(outcomes['Could not verify'])}"
        )
    if errors:
        raise click.ClickException("; ".join(errors))

    click.echo("Finished removing user from projects")


if __name__ == "__main__":
    remove_user()
