"""Script to calculate cost average, stdev, cheapest, and most expensive tasks in a project"""

import click
import time
import statistics
from matplotlib import pyplot as plt
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--status",
    help="comma-separated list of task statuses to find",
    default="COMPLETED",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
def find_tasks(project, profile, status):
    """Find a file in a project"""
    # read config file
    api = hf.parse_config(profile)

    # get all tasks in project
    all_tasks = hf.get_all_tasks(api, project)

    stati = status.split(",")

    costs = {}

    for task in all_tasks:
        if task.status in stati:
            my_id = task.id
            my_app = task.app
            my_price = task.price.amount

            # fill all lists
            if "all" in costs.keys():
                costs["all"]["prices"].append(my_price)
                if my_price <= costs["all"]["lowest"]:
                    costs["all"]["lowest"] = my_price
                    costs["all"]["lowest_id"] = my_id
                if my_price >= costs["all"]["highest"]:
                    costs["all"]["highest"] = my_price
                    costs["all"]["highest_id"] = my_id
            else:
                costs["all"] = {}
                costs["all"]["highest"] = my_price
                costs["all"]["lowest"] = my_price
                costs["all"]["highest_id"] = my_id
                costs["all"]["lowest_id"] = my_id
                costs["all"]["prices"] = [my_price]

            # fill app specifics
            if my_app in costs.keys():
                costs[my_app]["prices"].append(my_price)
                if my_price <= costs["all"]["lowest"]:
                    costs[my_app]["lowest"] = my_price
                    costs[my_app]["lowest_id"] = my_id
                if my_price >= costs["all"]["highest"]:
                    costs[my_app]["highest"] = my_price
                    costs[my_app]["highest_id"] = my_id
            else:
                costs[my_app] = {}
                costs[my_app]["highest"] = my_price
                costs[my_app]["lowest"] = my_price
                costs[my_app]["highest_id"] = my_id
                costs[my_app]["lowest_id"] = my_id
                costs[my_app]["prices"] = [my_price]

    # format final output and do stats
    print(
        "\t".join(
            [
                "app_name",
                "task count",
                "total cost",
                "average cost",
                " cost stdev",
                "highest task id",
                "highest cost",
                "lowest task id",
                "lowest cost",
            ]
        )
    )
    for app in costs:
        app_name = app
        if len(app.split('/')) > 1:
            app_name = app.split('/')[-2]
        total = sum(costs[app]["prices"])
        count = len(costs[app]["prices"])
        average = total / count
        stdev = None
        if total > 1:
            stdev = statistics.stdev(costs[app]["prices"])
        highest_cost = costs[app]["highest"]
        highest_id = costs[app]["highest_id"]
        lowest_cost = costs[app]["lowest"]
        lowest_id = costs[app]["lowest_id"]
        print(
            f"{app_name}\t{count}\t{total}\t{average}\t{stdev}\t{highest_id}\t{highest_cost}\t{lowest_id}\t{lowest_cost}"
        )
        plt.hist(costs[app]["prices"])

        # Adding labels and a title for clarity
        plt.xlabel("Value")
        plt.ylabel("Frequency")
        plt.title(f"Histogram of {app_name} Prices")

        # Displaying the plot
        plt.show()


if __name__ == "__main__":
    find_tasks()
