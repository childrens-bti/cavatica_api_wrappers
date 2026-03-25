"""Generate a report of all projects the user created and who's in it"""

import click
import time
from sevenbridges import Api
from helper_functions import helper_functions as hf

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

    pcs = project_creator.split(",")

    for p in projs:
        if p.id.split("/")[0] in pcs:
            users = p.get_members()
            usernames = [user.username for user in users]
            if user not in usernames:
                new_member = p.add_member(
                    user=user,
                    permissions={
                        "read": True,
                        "write": True,
                        "execute": True,
                        "copy": True,
                        "admin": admin,
                    },
                )
                print(f"Added {user} to {p.id}")

    print("Finished adding user to projects")

if __name__ == "__main__":
    project_report()
