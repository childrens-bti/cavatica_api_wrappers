"""Generate a report of all projects the user created and who's in it"""

import click
import time
from sevenbridges import Api
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
@click.option(
    "--project_creator",
    help="Username(s) of project creator to check for",
    required=True,
)
@click.option(
    "--admin", help="Flag to grant user admin permissions", is_flag=True, default=False
)
def project_report(profile, user, project_creator, admin):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    projs = hf.get_all_projects(api)

    pcs = set(project_creator.split(","))

    for p in tqdm(projs, desc="Adding user to projects", unit="project"):
        if p.id == "childrens-bti/childrens-bti-references":
            continue
        if p.id.split("/")[0] in pcs:
            try:
                users = p.get_members()
                usernames = {member.username for member in users}
                if user not in usernames:
                    p.add_member(
                        user=user,
                        permissions={
                            "read": True,
                            "write": True,
                            "execute": True,
                            "copy": True,
                            "admin": admin,
                        },
                    )
            except Forbidden:
                tqdm.write(f"Insufficient permissions for {p.id}; skipping")

    print("Finished adding user to projects")

if __name__ == "__main__":
    project_report()
