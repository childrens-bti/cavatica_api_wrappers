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

    for p in projs:
        if p.id.split("/")[0] == me.username:
            correct_permissions = False
            permission_count = 0
            link = f"{base_link}{p.id}"
            users = p.get_members()
            usernames = []
            for user in users:
                username = user.username
                if username in ["sicklera", "harenzaj", "chaodi"]:
                    if user.permissions["admin"] == True:
                        permission_count += 1
                usernames.append(username)
            if permission_count == 3:
                correct_permissions = True
            print(f"{p.id}\t{",".join(usernames)}\t{link}\t{correct_permissions}")


if __name__ == "__main__":
    project_report()
