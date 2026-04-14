"""Non-default inputs for a task."""

import sys
import click
import pandas as pd
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import NotFound
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def get_printable(in_obj, api):
    """
    Get a printable version of an object.
    I'm sure there's a smarter way to do this.
    Inputs:
    - in_obj: the object to get a printable version of
    - api: the api object to use for getting file objects
    Returns:
    - out_obj: a printable version of the input object
    """
    out_obj = in_obj

    if (
        type(in_obj) is str
        or type(in_obj) is int
        or type(in_obj) is float
        or type(in_obj) is bool
    ):
        out_obj = str(in_obj)
    else:
        # probably a file object, try it?
        try:
            file_obj = api.files.get(id=in_obj)
            out_obj = file_obj.name
        except Exception as e:
            print(
                f"Can't find {in_obj}, file doesn't exist",
                file=sys.stderr,
            )
            exit(1)

    return out_obj


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--task_file", help="File with task ids")
@click.option("--task_id", help="Task id")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def get_task_files(task_file, task_id, profile, debug):
    """
    Get the non-default task inputs for a task or list of tasks.
    """
    # read config file
    api = hf.parse_config(profile)

    # get all of the tasks either from --task_id or reading the --task_file file
    all_tasks = []
    if task_file and task_id:
        print("ERROR: Please provide either a task file or a task id", file=sys.stderr)
        exit(1)
    elif task_id:
        all_tasks.append(api.tasks.get(id=task_id))
    elif task_file:
        with open(task_file, "r") as f:
            for line in f:
                task_id = line.strip()
                all_tasks.append(api.tasks.get(id=task_id))

    # not sure if .inputs gives us all or just non-default....
    # feels like somewhere in between???
    # maybe because "default" and "suggested" are different?
    series_dict = {}
    for task in all_tasks:
        s = pd.Series(dtype="object")
        s["project"] = task.project
        s["Task id"] = task.id
        t_name = task.name.replace(" ", "_")
        s["Task name"] = t_name
        s["Task status"] = task.status
        for inp in task.inputs:
            if task.inputs[inp] is not None:
                if debug:
                    print(f"Input name:{inp}")
                    print(f"Input value:{task.inputs[inp]}")
                    print(f"Input type:{type(task.inputs[inp])}")
                if type(task.inputs[inp]) is list:
                    all_objs = []
                    for item in task.inputs[inp]:
                        if type(item) is list:
                            for sub in item:
                                obj = get_printable(sub, api)
                                all_objs.append(obj)
                        else:
                            obj = get_printable(item, api)
                            all_objs.append(obj)
                    s[inp] = ",".join(all_objs)
                else:
                    obj = get_printable(task.inputs[inp], api)
                    s[inp] = obj
        series_dict[task.id] = s

    # write to spreadsheet as one series per task
    out_spreadsheet = Path(f"task_inputs.xlsx")
    with pd.ExcelWriter(out_spreadsheet) as writer:
        for key, s in series_dict.items():
            sheet = key.replace(":", "_")
            if debug:
                print(f"Writing task {key} to {out_spreadsheet}")
            s.to_frame(name="value").to_excel(writer, sheet_name=sheet, index=True)

    print("DONE!")


if __name__ == "__main__":
    get_task_files()
