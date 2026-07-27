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


def wrap_file_obj(api, project, cur_input):
    """
    Wrapper function for get_file_obj.
    Tries to handle index files

    Inputs:
    - api: sevenbridges Api object
    - project: project id
    - cur_input: file name or id

    Returns:
    - file_id: file id
    """
    my_indices = (".crai", ".tbi", ".bai", ".fai")
    path = Path(cur_input)
    suff = path.suffix
    if suff in my_indices:
        main_file = path.stem
        print(f"Found index file {cur_input}, trying to get main file {main_file}")
        try:
            # return hf.get_file_obj(api, project, main_file)
            main_obj = hf.get_file_obj(api, project, main_file)
            raise ValueError(
                f"Index file given. Update options file to include {main_file} instead of {cur_input}"
            )
        except FileNotFoundError as exc:
            raise ValueError(
                f"Main file {main_file} for index {cur_input} was not found"
            ) from exc

    return hf.get_file_obj(api, project, cur_input)


def get_input_type(my_input):
    """
    Get input type

    Inputs:
    - my_input: type key from workflow input

    Returns:
    - input_type: str input type (file, bool, int, or float)
    - array: boolean True if input is an array
    """
    is_array = False
    in_type = None

    if isinstance(my_input, list):
        # in_type = "string"
        for inp in my_input:
            if inp != "null":
                in_type, array_input = get_input_type(inp)
                if array_input:
                    is_array = True
    elif isinstance(my_input, dict):
        # this probably isn't needed nor and might not even be correct for enums...
        if my_input["type"] in ["File", "Directory"]:
            in_type = "file"
        elif my_input["type"] == "boolean":
            in_type = "bool"
        elif my_input["type"] == "int":
            in_type = "int"
        elif my_input["type"] == "float":
            in_type = "float"
        elif my_input["type"] == "array":
            in_type, array_input = get_input_type(my_input["items"])
            is_array = True
        else:
            in_type = "string"
    else:
        if "[]" in my_input:
            is_array = True
        if my_input.startswith("File"):
            in_type = "file"
        elif my_input.startswith("Directory"):
            in_type = "file"
        elif my_input.startswith("boolean"):
            in_type = "bool"
        elif my_input.startswith("int"):
            in_type = "int"
        elif my_input.startswith("float"):
            in_type = "float"
        elif my_input.startswith("double"):
            in_type = "double"
        else:
            in_type = "string"

    return in_type, is_array


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
                # if inputs are a list, the input workflow is stricter yaml format
                # likely exported from Cavatica
                if isinstance(inputs, list):
                    workflow_inputs[input["id"]], array_input = get_input_type(
                        input["type"]
                    )
                    if array_input:
                        array_inputs.append(input["id"])
                elif isinstance(inputs[input], str):
                    if "[]" in inputs[input]:
                        array_inputs.append(input)
                    workflow_inputs[input] = "string"
                elif isinstance(inputs[input], dict):
                    workflow_inputs[input], array_input = get_input_type(
                        inputs[input]["type"]
                    )
                    if array_input:
                        array_inputs.append(input)

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
    "-w",
    "--workflow_file",
    type=click.Path(exists=True),
    help="Path to workflow file",
)
@click.option("--out", help="Output files basename", default="new")
@click.option(
    "--options_file",
    type=click.Path(exists=True),
    help="Path to options file",
)
def create_task_script(profile, workflow_file, out, options_file):
    """
    Create a draft task from a workflow cwl and file with task options.
    """

    today = datetime.datetime.now().strftime("%Y%m%d")

    # get api
    api = hf.parse_config(profile)
    username = api.users.me().username

    # parse workflow file
    workflow_inputs, array_inputs = parse_workflow_file(workflow_file)

    # parse options file and create tasks
    task_ids = []
    file_ids = {}
    out_lines = []
    new_cols = ["task_id", "created_by"]
    base_names = {}
    our_app = None
    with open(options_file, "r") as f:
        line_num = 0
        task_options = []
        app_index = None
        for line in f:
            if line_num == 0:
                # parse header
                head_line = line.strip()
                task_options = head_line.split("\t")
                for opt in task_options:
                    if "output_basename" in opt:
                        base_names[opt] = {"out_name": f"final_{opt}", "value": None}
                head_line = f"{head_line}\t{"\t".join(new_cols)}\t{"\t".join([base_names[opt]["out_name"] for opt in base_names])}"
                out_lines.append(head_line)
                # find the app index in the task options, then remove it
                if "app" in task_options:
                    app_index = task_options.index("app")
                    task_options.remove("app")
                else:
                    raise ValueError(
                        f"App not in options file header: {head_line}. Please add app column to options file."
                    )
            else:
                # create new task reading inputs and converting to expected type
                task_inputs = {}
                line_split = line.strip().split("\t")
                app = line_split[app_index]
                if our_app is None:
                    our_app = app
                elif our_app != app:
                    raise ValueError(
                        f"App {app} does not match previous app {our_app}. Please use the same app for all tasks."
                    )
                project_id = "/".join(app.split("/")[:2])
                project = hf.parse_project(project_id)
                # remove app from line_split
                line_split.remove(app)
                for option in task_options:
                    if option not in workflow_inputs:
                        print(
                            f"Option {option} not in workflow inputs: {workflow_inputs}"
                        )
                        exit(1)
                    else:
                        if option not in array_inputs:
                            cur_input = line_split[task_options.index(option)]
                            if workflow_inputs[option] == "file":
                                if cur_input in file_ids:
                                    task_inputs[option] = file_ids[cur_input]
                                else:
                                    my_id = wrap_file_obj(api, project, cur_input)
                                    task_inputs[option] = my_id
                                    file_ids[cur_input] = my_id
                            elif workflow_inputs[option] == "bool":
                                task_inputs[option] = (
                                    cur_input.strip().lower() == "true"
                                )
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
                                    if task_inputs[option][i] in file_ids:
                                        task_inputs[option][i] = file_ids[
                                            task_inputs[option][i]
                                        ]
                                    else:
                                        my_id = wrap_file_obj(
                                            api, project, task_inputs[option][i]
                                        )
                                        file_ids[task_inputs[option][i]] = my_id
                                        task_inputs[option][i] = my_id
                                elif workflow_inputs[option] == "bool":
                                    task_inputs[option][i] = (
                                        task_inputs[option][i].strip().lower() == "true"
                                    )
                                elif workflow_inputs[option] == "int":
                                    task_inputs[option][i] = int(task_inputs[option][i])
                                elif workflow_inputs[option] == "float":
                                    task_inputs[option][i] = float(
                                        task_inputs[option][i]
                                    )
                                else:
                                    task_inputs[option][i] = task_inputs[option][i]

                app_name = app.split("/")[2]
                task_name = f"{app_name}_{today}"
                if "output_basename" in task_inputs:
                    task_name = f"{task_name}_{task_inputs["output_basename"]}"
                else:
                    task_name = f"{task_name}_{line_num}"

                # call api and store task_id
                new_task = api.tasks.create(
                    name=task_name, project=project, app=app, inputs=task_inputs
                )

                # update task now that we have task id
                if base_names:
                    for base in base_names:
                        if new_task.inputs[base] is not None:
                            base_names[base][
                                "value"
                            ] = f"{new_task.inputs[base]}_{new_task.id}"
                            new_task.inputs[base] = base_names[base]["value"]
                        else:
                            base_names[base]["value"] = new_task.id
                            new_task.inputs[base] = base_names[base]["value"]

                    new_task.save()

                print(f"{new_task.name}, {new_task.status}, {new_task.id}")
                task_ids.append(new_task.id)
                out_lines.append(
                    f"{line.strip()}\t{new_task.id}\t{username}\t{"\t".join([base_names[opt]["value"] for opt in base_names])}"
                )

            line_num += 1

    # output task ids to file
    task_file = f"{out}_task_ids.txt"
    with open(task_file, "w") as f:
        for task_id in task_ids:
            f.write(f"{task_id}\n")

    # rewrite options file with new columns for
    # task id, creator, and updated output basenames
    options_out_file = f"{out}_options.tsv"
    with open(options_out_file, "w") as f:
        for line in out_lines:
            f.write(f"{line}\n")


if __name__ == "__main__":
    create_task_script()
