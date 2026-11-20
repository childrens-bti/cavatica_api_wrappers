"""Script to make a Cavatica project from an issue template"""

import os
import click
import re
from sevenbridges import Api
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper
from helper_functions import helper_functions as hf

ADMIN_USERS = ["sicklera", "harenzaj", "farrow1"]
REGULAR_USERS = ["chaodi", "corbettr", "raqureshi"]
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def parse_selections(value):
    """Parse checked labels or comma-separated values from an issue form."""
    if not value.strip() or value.strip() == "_No response_":
        return []

    checkbox_matches = re.findall(
        r"^- \[(?P<checked>[ xX])\][ \t]*(?P<label>[^\r\n]+)",
        value,
        flags=re.MULTILINE,
    )
    if checkbox_matches:
        return [
            label.strip()
            for checked, label in checkbox_matches
            if checked.lower() == "x"
        ]

    return [item.strip() for item in value.split(",") if item.strip()]


def parse_users(value):
    """Parse additional users selected in the issue form."""
    return parse_selections(value)


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

    body = os.environ["BODY"]
    description = os.environ["URL"]

    fields = re.split(r"^### ", body, flags=re.MULTILINE)

    # default to AWS-BTI-Core
    billing_id = "9fbf675f-6525-4dff-bf55-778a4528c936"
    project = None
    user_list = []
    tags = []

    # the split makes a blank first field so skip it
    fields = fields[1:]

    # read the fields and create project inputs
    for field in fields:
        pair = re.split(r"\r?\n\r?\n", field, maxsplit=1)
        key = pair[0].strip()
        value = pair[1].strip()
        if key == "Billing":
            for billing_group in billing_groups:
                if billing_group.name == value:
                    billing_id = billing_group.id
        elif key == "Project_Name":
            project = value
        elif key == "Users":
            user_list = parse_users(value)
        elif key in {"PI", "Project", "Experimental_Strategy", "dev"}:
            tags.extend(parse_selections(value))
        else:
            raise ValueError(f"Unknown field: {key}")

    user_list = list(dict.fromkeys(user_list + REGULAR_USERS))
    tags = list(dict.fromkeys(tags))

    # create project
    if run:
        print("Creating project")
        new_project = api.projects.create(
            name=project,
            billing_group=billing_id,
            description=description,
            tags=tags,
            settings={"use_memoization": True, "allow_network_access": True},
        )
        print("Adding admin users")
        for user in ADMIN_USERS:
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
                if user not in ADMIN_USERS:
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
        print(f"tags={tags}")


if __name__ == "__main__":
    create_project()
