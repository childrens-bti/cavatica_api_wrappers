"""Find and log files in a project"""

import click
from sevenbridges import Api
from sevenbridges.errors import SbgError
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--project", help="Project ID")
@click.option("--task_file", help="File with task ids")
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
@click.option(
    "--output_file",
    "-o",
    help="Output filename",
)
def find_logs(profile, project, task_file, debug, output_file):
    """Find log files in a project"""

    # read config file
    api = hf.parse_config(profile)

    # get all tasks or a list of tasks in a project
    tasks = []
    if project and task_file:
        raise ValueError("Either 'project' or 'task_file' must be set. Not Both.")
    elif project:
        tasks = hf.get_all_tasks(api, project)
    elif task_file:
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                task = api.tasks.get(id=task_id)
                tasks.append(task)
    else:
        raise ValueError("Either 'project' or 'task_file' must be set.")

    out_strings = []

    for task in tasks:

        if debug:
            print(task.name)

        if task.status == "COMPLETED":
            # get task details
            exec_dets = task.get_execution_details()
            task_jobs = exec_dets.jobs
            for job in task_jobs:
                for log in job.logs:
                    #if job.logs[log] is not None:
                    try:
                        log_name = job.logs[log].name
                        log_id = job.logs[log].id
                        out_strings.append(
                            f"{task.name}\t{job.name}\t{log_name}\t{log_id}"
                        )
                    except Exception as e:
                        continue


    # write out_strings to output file
    if output_file:
        with open(output_file, "w") as out_f:
            if debug:
                out_f.write("Task_Name\tJob_Name\tLog_Name\tLog_ID\n")
            for out_str in out_strings:
                out_f.write(f"{out_str}\n")
    else:
        print("Task_Name\tJob_Name\tLog_Name\tLog_ID")
        for out_str in out_strings:
            print(out_str)


if __name__ == "__main__":
    find_logs()
