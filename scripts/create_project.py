"""Simple script to find a file in a project"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

#DEFAULT_USERS = ["sicklera", "harenzaj", "chaodi", "corbettr"]
DEFAULT_USERS = ["harenzaj", "chaodi", "corbettr"]
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project name")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--billing", help="Billing group name")
@click.option(
    "--users",
    help="Comma separated list of additional users to add to project. See code for default users",
)
@click.option("--description", help="Optional, project description", default=None)
@click.option("--run", help="Run the export job", is_flag=True, default=False)
def create_project(project, profile, billing, users, description, run):
    """Create a project and add billing group"""
    # read config file
    api = hf.parse_config(profile)

    # get billing group id
    billing_groups = hf.get_all_billing(api)

    billing_id = None

    for billing_group in billing_groups:
        if billing_group.name == billing:
            billing_id = billing_group.id

    # create project
    if run:
        print("Creating project")
        new_project = api.projects.create(
            name=project, billing_group=billing_id, description=description
        )
        # add users to project
        print("Adding admin users")
        for user in DEFAULT_USERS:
            new_member = new_project.add_member(
                user=user,
                permissions={
                    "read": True,
                    "write": True,
                    "execute": True,
                    "admin": True,
                },
            )
        print("Adding regular users")
        if users:
            user_list = users.split(",")
            for user in user_list:
                new_member = new_project.add_member(
                    user=user,
                    permissions={
                        "read": True,
                        "write": True,
                        "execute": True,
                    },
                )
        print(f"Created project: {new_project.name}: {new_project.id}")
    else:
        print("DRY RUN!")
        print("Attempting to create project with these inputs:")
        print(f"name={project}")
        print(f"billing_group={billing_id}")
        print(f"description={description}")


if __name__ == "__main__":
    create_project()
