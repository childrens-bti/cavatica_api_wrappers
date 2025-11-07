"""Script to make a Cavatica project from an issue template"""

import os
import click
import re
from sevenbridges import Api
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper
from helper_functions import helper_functions as hf

# DEFAULT_USERS = ["sicklera", "harenzaj", "chaodi", "corbettr"]
DEFAULT_USERS = ["harenzaj", "chaodi", "corbettr"]
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--token", help="Cavatica token value")
@click.option("--run", help="Flag to create project", is_flag=True, default=False)
def create_project(token, run):
    """Create a project in Cavatica"""

    # create api
    api = Api(
        url="https://cavatica-api.sbgenomics.com/v2",
        token=token,
        error_handlers=[rate_limit_sleeper, maintenance_sleeper],
    )

    billing_groups = hf.get_all_billing(api)

    body = os.environ['BODY']
    description = os.environ['URL']

    print(body)

    fields = re.split(r"### ", body)

    billing_id = None
    project = None
    user_list = None

    # the split makes a blank first field so skip it
    fields = fields[1:]

    # read the fields and create project inputs
    for field in fields:
        pair = re.split(r"\\n\\n", field)
        key = pair[0]
        value = pair[1]
        if key == "Billing":
            for billing_group in billing_groups:
                if billing_group.name == value:
                    billing_id = billing_group.id
        elif key == "Project_Name":
            project = value
        elif key == "Users":
            if "No response" not in value:
                users = value
                if " " in users:
                    users = value.replace(" ", "")
                user_list = users.split(",")
        else:
            raise ValueError(f"Unknown field: {key}")

    # create project
    if run:
        print("Creating project")
        new_project = api.projects.create(
            name=project,
            billing_group=billing_id,
            description=description,
            settings={"use_memoization": True, "allow_network_access": True},
        )
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
        if user_list:
            for user in user_list:
                if user not in DEFAULT_USERS:
                    new_member = new_project.add_member(
                        user=user,
                        permissions={
                            "read": True,
                            "write": True,
                            "execute": True,
                            "copy": True,
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
