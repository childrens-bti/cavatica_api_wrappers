"""Delete output files from failed tasks"""

import click
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url"
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option(
    "--abort",
    help="Also delete output file from ABORTED tasks",
    is_flag=True,
    default=False,
)
@click.option("--run", help="Run the task", is_flag=True, default=False)
def delete_failed_output_files(profile, project, abort, run):
    """
    Find failed tasks and delte the outputs from those tasks.
    """

    api = hf.parse_config(profile)

    # get failed tasks in project
    all_tasks = hf.get_all_tasks(api, project)

    my_stati = ["FAILED"]
    if abort:
        my_stati.append("ABORTED")

    failed_tasks = []
    for task in all_tasks:
        if task.status in my_stati:
            failed_tasks.append(task)

    for task in failed_tasks:
        print(f"{task.id}, {task.name}, {task.status}")

        # get files
        files = []
        for out_key in task.outputs.keys():
            if type(task.outputs[out_key]) is list:
                for file in task.outputs[out_key]:
                    if type(file) is list:
                        for f in file:
                            files.append(f)
                    elif file is not None:
                        files.append(file)
            elif task.outputs[out_key] is not None:
                files.append(task.outputs[out_key])

        print(f"Found {len(files)} files")

        for file in files:
            # add any secondary files
                if file.secondary_files is not None:
                    for secondary in file.secondary_files:
                        # check if secondary already in list
                        if secondary not in files:
                            files.append(secondary)

        if run:
            for file in files:
            # add any secondary files
                if file.secondary_files is not None:
                    for secondary in file.secondary_files:
                        # check if secondary already in list
                        if secondary not in files:
                            files.append(secondary)

                try:
                    file.delete()
                except NotFound:
                    print("File already deleted, skipping")

    print("Done!")


if __name__ == "__main__":
    delete_failed_output_files()
