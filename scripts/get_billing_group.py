"""Simple script to find a billing group"""

import click
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--group_name", help="File name")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_billing_group(group_name, profile):
    """Find a billing group"""
    # read config file
    api = hf.parse_config(profile)

    # get all billing groups the user has access to
    # might need to add pagination???
    billing_groups = hf.get_all_billing(api)

    billing = None

    for billing_group in billing_groups:
        #print(f"{billing_group.name}\t{billing_group.id}")
        if billing_group.name == group_name:
            billing = billing_group

    print(f"{billing.name}\t{billing.id}")
    #print(dir(my_billing))
    #print(dir(my_billing.breakdown()))
    #print(my_billing.storage_breakdown())

    # get all storage breakdowns
    # will also need to handle limists here
    """
    for sb in billing.storage_breakdown():
        print(sb.project_name)
        for pb in sb.project_breakdown:
            print(dir(pb))
    """

    # get all analysis breakdowns


if __name__ == "__main__":
    find_billing_group()
