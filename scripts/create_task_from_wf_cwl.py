"""Create a draft task from a workflow cwl"""

import click
import sys
import yaml
import datetime
import time
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def parse_workflow_file(workflow_file):
    """
    Parse workflow file and return inputs
    """
    workflow_inputs = {}
    array_inputs = []
    with open(workflow_file, "r") as stream:
        try:
            workflow = yaml.safe_load(stream)
            inputs = workflow["inputs"]
            for input in inputs:
                # figure out input type
                if isinstance(inputs[input], str):
                    workflow_inputs[input] = "string"
                elif isinstance(inputs[input], dict):
                    for key in inputs[input]:
                        if key == "type":
                            if isinstance(inputs[input][key], list):
                                workflow_inputs[input] = "string"
                            elif isinstance(inputs[input][key], dict):
                                if inputs[input][key]["type"] == "File":
                                    # this probably isn't needed nor and might not even be correct for enums...
                                    workflow_inputs[input] = "file"
                                elif inputs[input][key]["type"] == "boolean":
                                    workflow_inputs[input] = "bool"
                                elif inputs[input][key]["type"] == "int":
                                    workflow_inputs[input] = "int"
                                elif inputs[input][key]["type"] == "float":
                                    workflow_inputs[input] = "float"
                                else:
                                    workflow_inputs[input] = "string"
                            else:
                                if "[]" in inputs[input][key]:
                                    array_inputs.append(input)
                                if inputs[input][key].startswith("File"):
                                    workflow_inputs[input] = "file"
                                elif inputs[input][key].startswith("boolean"):
                                    workflow_inputs[input] = "bool"
                                elif inputs[input][key].startswith("int"):
                                    workflow_inputs[input] = "int"
                                elif inputs[input][key].startswith("float"):
                                    workflow_inputs[input] = "float"
                                else:
                                    workflow_inputs[input] = "string"
        except yaml.YAMLError as exc:
            print(exc)
            exit(1)
    print("Done processing workflow inputs!", file=sys.stderr)
    return workflow_inputs, array_inputs


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option(
    "--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url"
)
@click.option("--app", help="App name, appid field on Cavaita app page")
@click.option(
    "-w",
    "--workflow_file",
    type=click.Path(exists=True),
    help="Path to workflow file",
)
@click.option("--out", help="Output file", default="new_task_ids.txt")
@click.option(
    "--skip_name_check",
    help="Skip checking if app name and workflow file name match",
    is_flag=True,
    default=False,
)
@click.option(
    "--options_file",
    type=click.Path(exists=True),
    help="Path to options file",
)
def create_task_script(
    profile, project, app, workflow_file, out, skip_name_check, options_file
):
    """
    Create a draft task launch script from a template and workflow cwl.
    """

    today = datetime.datetime.now().strftime("%Y%m%d")

    # get api
    api = hf.parse_config(profile)

    web_app_name = app.split("/")[-1]
    file_app_name = workflow_file.split("/")[-1].split(".")[0]
    if web_app_name != file_app_name:
        if not skip_name_check:
            print("App name and workflow file name do not match")
            exit(1)

    # prase workflow file
    workflow_inputs, array_inputs = parse_workflow_file(workflow_file)

    # parse options file and create tasks
    task_ids = []
    with open(options_file, "r") as f:
        line_num = 0
        task_options = []
        for line in f:
            if line_num == 0:
                # parse header
                task_options = line.strip().split("\t")
            else:
                # create new task reading inputs and converting to expected type
                task_inputs = {}
                line_split = line.strip().split("\t")
                for option in task_options:
                    if option not in workflow_inputs:
                        print(f"Option {option} not in workflow inputs: {workflow_inputs}")
                        exit(1)
                    else:
                        if option not in array_inputs:
                            cur_input = line_split[task_options.index(option)]
                            if workflow_inputs[option] == "file":
                                task_inputs[option] = hf.get_file_obj(
                                    api, project, cur_input
                                )
                            elif workflow_inputs[option] == "bool":
                                task_inputs[option] = cur_input.lower() == "true"
                            elif workflow_inputs[option] == "int":
                                task_inputs[option] = int(cur_input)
                            elif workflow_inputs[option] == "float":
                                task_inputs[option] = float(cur_input)
                            else:
                                task_inputs[option] = cur_input
                        else:
                            task_inputs[option] = line_split[
                                task_options.index(option)
                            ].split(",")
                            for i in range(len(task_inputs[option])):
                                if workflow_inputs[option] == "file":
                                    task_inputs[option][i] = hf.get_file_obj(
                                        api, project, task_inputs[option][i]
                                    )
                                elif workflow_inputs[option] == "bool":
                                    task_inputs[option][i] = (
                                        task_inputs[option][i].lower() == "true"
                                    )
                                elif workflow_inputs[option] == "int":
                                    task_inputs[option][i] = int(task_inputs[option][i])
                                elif workflow_inputs[option] == "float":
                                    task_inputs[option][i] = float(
                                        task_inputs[option][i]
                                    )
                                else:
                                    task_inputs[option][i] = task_inputs[option][i]

                task_name = f"{web_app_name}_{today}"
                if "output_basename" in task_inputs:
                    task_name = f"{task_name}_{task_inputs["output_basename"]}"
                else:
                    task_name = f"{task_name}_{line_num}"

                # call api and store task_id
                new_task = api.tasks.create(
                    name=task_name, project=project, app=app, inputs=task_inputs
                )
                print(f"{new_task.name}, {new_task.status}, {new_task.id}")
                task_ids.append(new_task.id)

            line_num += 1

    # output task ids to file
    with open(out, "w") as f:
        for task_id in task_ids:
            f.write(f"{task_id}\n")


if __name__ == "__main__":
    create_task_script()
