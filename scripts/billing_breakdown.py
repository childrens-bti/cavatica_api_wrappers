"""Simple script to find a billing group"""

import click
import datetime
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--group_name", help="File name", default = "AWS-BTI-Core")
@click.option("--start_date", help="Start date in mm-dd-yyyy format")
@click.option("--end_date", help="End date in mm-dd-yyyy format")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_billing_group(group_name, profile, start_date, end_date):
    """Find a billing group"""

    if not end_date:
        end_date = datetime.datetime.now().strftime("%m-%d-%Y")

    if not start_date:
        start_date = datetime.datetime.today() - datetime.timedelta(weeks=1)
        start_date = start_date.strftime("%m-%d-%Y")

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

    for sb in billing.storage_breakdown(date_from=start_date, date_to=end_date):
        print(f"{sb.project_name}\t{sb.active.cost.amount}")
    

    # get all analysis breakdowns


if __name__ == "__main__":
    find_billing_group()
