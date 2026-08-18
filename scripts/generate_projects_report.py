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
def project_report(profile):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    base_link = "https://cavatica.sbgenomics.com/u/"

    me = api.users.me()

    projs = hf.get_all_projects(api)

    print("project\tusers\turl\tcorrect permissions")

    owned_project_prefix = f"{me.username}/"
    expected_admins = {"sicklera", "harenzaj", "chaodi"}
    for p in projs:
        if not p.id.startswith(owned_project_prefix):
            continue

        permission_count = 0
        link = f"{base_link}{p.id}"
        usernames = []
        for user in p.get_members():
            username = user.username
            usernames.append(username)
            if username in expected_admins and user.permissions["admin"] == True:
                permission_count += 1

        correct_permissions = permission_count == len(expected_admins)
        print(f"{p.id}\t{",".join(usernames)}\t{link}\t{correct_permissions}")


if __name__ == "__main__":
    project_report()
