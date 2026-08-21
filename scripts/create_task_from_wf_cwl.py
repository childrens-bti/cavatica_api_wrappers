"""Create a draft task from a workflow cwl"""

import click
import csv
import json
import sys
import datetime
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
TASK_API_WORKERS = 8


def wrap_file_obj(api, project, cur_input, file_dict, reject_indices=False):
    """
    Wrapper function to get file id.
    Tries to handle index files

    Inputs:
    - api: sevenbridges Api object
    - project: project id
    - cur_input: file name or id
    - file_dict: dictionary of file names to ids

    Returns:
    - file_id: file id
    """
    my_indices = (".crai", ".tbi", ".bai", ".fai")
    path = Path(cur_input)
    suff = path.suffix
    if reject_indices and suff in my_indices:
        main_file = path.stem
        print(f"Found index file {cur_input}, trying to get main file {main_file}")
        if main_file in file_dict:
            raise ValueError(
                f"Index file given. Update options file to include {main_file} instead of {cur_input}"
            )
        raise ValueError(
            f"Main file {main_file} for index {cur_input} was not found"
        )

    try:
        matching_files = file_dict[cur_input]
    except KeyError as exc:
        raise FileNotFoundError(
            f"ERROR: File {cur_input} not found in project {project}"
        ) from exc
    if len(matching_files) > 1:
        file_ids = ", ".join(file_obj.id for file_obj in matching_files)
        raise ValueError(
            f"Duplicate file name {cur_input!r} found for file ids {file_ids}"
        )
    return matching_files[0]


def parse_app_id(app):
    """Return the project and app name from an app ID, with an optional revision."""
    parts = app.strip("/").split("/")
    if len(parts) not in (3, 4) or not all(parts):
        raise click.UsageError(
            "JSON app must use the format user/project/app or user/project/app/revision"
        )
    return "/".join(parts[:2]), parts[2]


def load_task_inputs_json(path):
    """Load and validate inputs for one JSON-backed task."""
    try:
        with open(path, "r") as handle:
            task_inputs = json.load(handle)
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"Task inputs JSON is not valid JSON: {path}: {exc}"
        ) from exc

    if not isinstance(task_inputs, dict):
        raise click.ClickException("Task inputs JSON must contain one JSON object")

    app = task_inputs.pop("app", None)
    if not isinstance(app, str) or not app.strip():
        raise click.ClickException(
            "Task inputs JSON must contain a non-empty string app"
        )

    output_basename = task_inputs.get("output_basename")
    if not isinstance(output_basename, str) or not output_basename.strip():
        raise click.ClickException(
            "Task inputs JSON must contain a non-empty string output_basename"
        )

    output_basename = output_basename.strip()
    task_inputs["output_basename"] = output_basename
    return task_inputs, app.strip(), output_basename


def validate_json_task_inputs(api, app, task_inputs):
    """Reject JSON keys that are not inputs for the selected app."""
    workflow_inputs, _, _ = parse_workflow_app(api, app)
    unknown = sorted(set(task_inputs) - set(workflow_inputs))
    if unknown:
        raise click.ClickException(
            "Task inputs contain option(s) not in the CAVATICA app: "
            + ", ".join(unknown)
        )


def check_task_errors(task):
    """Fail with the draft ID when CAVATICA reports task validation errors."""
    task_errors = getattr(task, "errors", None)
    if isinstance(task_errors, (dict, list, tuple)) and task_errors:
        raise click.ClickException(
            f"Draft task {task.id} was created with validation errors: "
            + json.dumps(task_errors, default=str)
        )


def create_task_from_spec(api, task_spec):
    """Create one draft task from a prepared task specification."""
    new_task = api.tasks.create(**task_spec)
    check_task_errors(new_task)
    return new_task


def save_task_outputs(task_and_bases):
    """Update and save output basenames for one created task."""
    task, bases = task_and_bases
    output_values = {}
    for base in bases:
        if task.inputs[base] is not None:
            output_value = f"{task.inputs[base]}_{task.id}"
        else:
            output_value = task.id
        task.inputs[base] = output_value
        output_values[base] = output_value
    task.save()
    return task, output_values


def create_task_from_json(
    api,
    username,
    app,
    project,
    app_name,
    task_inputs,
    original_output_basename,
    out,
    today,
):
    """Create and record one draft task from structured JSON inputs."""
    task_name = f"{app_name}_{today}_{original_output_basename}"
    new_task = api.tasks.create(
        name=task_name, project=project, app=app, inputs=task_inputs
    )
    check_task_errors(new_task)
    final_output_basename = f"{original_output_basename}_{new_task.id}"

    try:
        new_task.inputs["output_basename"] = final_output_basename
        new_task.save()
    except Exception as exc:
        raise click.ClickException(
            f"Draft task {new_task.id} was created, but updating output_basename failed: {exc}"
        ) from exc

    print(f"{new_task.name}, {new_task.status}, {new_task.id}")

    with open(f"{out}_task_ids.txt", "w") as handle:
        handle.write(f"{new_task.id}\n")

    with open(f"{out}_options.tsv", "w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "app",
                "task_id",
                "created_by",
                "original_output_basename",
                "final_output_basename",
            ]
        )
        writer.writerow(
            [
                app,
                new_task.id,
                username,
                original_output_basename,
                final_output_basename,
            ]
        )


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


def parse_workflow_app(api, app):
    """
    Parse workflow app and return inputs
    """
    workflow_inputs = {}
    array_inputs = []
    secondary_file_inputs = set()
    app_obj = api.apps.get(app)
    inputs = app_obj.raw["inputs"]
    for input in inputs:
        workflow_inputs[input["id"]], array_input = get_input_type(input["type"])
        if array_input:
            array_inputs.append(input["id"])
        if "secondaryFiles" in input:
            secondary_file_inputs.add(input["id"])

    print("Done processing workflow inputs!", file=sys.stderr)
    return workflow_inputs, array_inputs, secondary_file_inputs


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="cavatica",
    show_default=True,
)
@click.option("--out", help="Output files basename", default="new")
@click.option(
    "--options_file",
    type=click.Path(exists=True),
    help="Path to options file",
)
@click.option(
    "--task-inputs-json",
    type=click.Path(exists=True, dir_okay=False),
    help="JSON object containing inputs for one CAVATICA task",
)
def create_task_script(profile, out, options_file, task_inputs_json):
    """
    Create draft tasks from TSV options or one structured JSON input object.
    """

    if bool(options_file) == bool(task_inputs_json):
        raise click.UsageError(
            "Provide exactly one of --options_file or --task-inputs-json"
        )
    # Validate JSON before connecting to CAVATICA.
    json_task_inputs = None
    app = None
    json_output_basename = None
    if task_inputs_json:
        json_task_inputs, app, json_output_basename = load_task_inputs_json(
            task_inputs_json
        )
        project_id, web_app_name = parse_app_id(app)

    today = datetime.datetime.now().strftime("%Y%m%d")

    # get api
    api = hf.parse_config(profile)

    if task_inputs_json:
        validate_json_task_inputs(api, app, json_task_inputs)
        username = api.users.me().username
        project = hf.parse_project(project_id)
        create_task_from_json(
            api,
            username,
            app,
            project,
            web_app_name,
            json_task_inputs,
            json_output_basename,
            out,
            today,
        )
        return

    username = api.users.me().username
    # parse options file and create tasks
    task_ids_by_row = {}
    out_lines = []
    task_specs = []
    new_cols = ["task_id", "created_by"]
    all_project_files = {}
    base_names = {}
    our_app = None
    workflow_inputs = None
    array_inputs = None
    secondary_files = None
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
                    # first time seeing an app, get all files in project and parse workflow inputs
                    our_app = app
                    project, _ = parse_app_id(app)
                    all_project_files = hf.get_all_files(api, project)
                    # store all project files in a dictionary for faster lookup
                    # dictionary form: {file_name: whole file_obj}
                    all_project_file_dict = {}
                    for file_obj in all_project_files:
                        previous_file = all_project_file_dict.get(file_obj.name)
                        if previous_file is not None:
                            warnings.warn(
                                f"Duplicate file name {file_obj.name!r} found for file ids "
                                f"{previous_file.id} and {file_obj.id}"
                                f"This will be an error if a task tries to use {file_obj.name!r} as an input.",
                                UserWarning,
                                stacklevel=2,
                            )
                        all_project_file_dict[file_obj.name] = file_obj
                elif our_app != app:
                    raise ValueError(
                        f"App {app} does not match previous app {our_app}. Please use the same app for all tasks."
                    )
                if workflow_inputs is None:
                    workflow_inputs, array_inputs, secondary_files = parse_workflow_app(api, app)
                project_id = "/".join(app.split("/")[:2])
                project = hf.parse_project(project_id)
                # remove app from line_split
                del line_split[app_index]
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
                                my_id = wrap_file_obj(
                                    api,
                                    project,
                                    cur_input,
                                    all_project_file_dict,
                                    option in secondary_files,
                                )
                                task_inputs[option] = my_id
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
                                    my_id = wrap_file_obj(
                                        api,
                                        project,
                                        task_inputs[option][i],
                                        all_project_file_dict,
                                        option in secondary_files,
                                    )
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

                task_specs.append(
                    {
                        "name": task_name,
                        "project": project,
                        "app": app,
                        "inputs": task_inputs,
                    }
                )
                out_lines.append(line.strip())

            line_num += 1

    failed_rows = []
    saved_tasks = {}
    task_file = f"{out}_task_ids.txt"
    with open(task_file, "w"):
        pass

    # Submit all rows concurrently, but handle each result as soon as it is
    # available so successful IDs are durable even if another row fails.
    if task_specs:
        worker_count = min(TASK_API_WORKERS, len(task_specs))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            create_futures = {
                executor.submit(create_task_from_spec, api, task_spec): index
                for index, task_spec in enumerate(task_specs)
            }
            created_tasks = {}
            with open(task_file, "a") as task_handle:
                for future in as_completed(create_futures):
                    row_index = create_futures[future]
                    try:
                        new_task = future.result()
                    except Exception as exc:
                        failed_rows.append((row_index, exc))
                        continue
                    created_tasks[row_index] = new_task
                    task_ids_by_row[row_index] = new_task.id
                    task_handle.write(f"{new_task.id}\n")
                    task_handle.flush()

            save_futures = {
                executor.submit(
                    save_task_outputs,
                    (task, tuple(base_names)),
                ): row_index
                for row_index, task in created_tasks.items()
                if base_names
            }
            if not base_names:
                saved_tasks = {
                    row_index: (task, {})
                    for row_index, task in created_tasks.items()
                }
            for future in as_completed(save_futures):
                row_index = save_futures[future]
                try:
                    saved_tasks[row_index] = future.result()
                except Exception as exc:
                    failed_rows.append((row_index, exc))

    if failed_rows:
        failed_file = f"{out}_failed_rows.txt"
        with open(failed_file, "w") as handle:
            for row_index, exc in sorted(failed_rows):
                handle.write(
                    f"Input row {row_index + 2}: {out_lines[row_index + 1]}\n"
                    f"Error: {exc}\n\n"
                )
        raise click.ClickException(
            f"{len(failed_rows)} task row(s) failed. Successful task IDs were saved to "
            f"{task_file}; failed rows were saved to {failed_file}."
        )

    task_lines = out_lines[:1]
    for row_index, original_line in enumerate(out_lines[1:]):
        new_task, output_values = saved_tasks[row_index]
        print(f"{new_task.name}, {new_task.status}, {new_task.id}")
        task_lines.append(
            f"{original_line}\t{new_task.id}\t{username}\t"
            + "\t".join(output_values[opt] for opt in base_names)
        )
    out_lines = task_lines

    # rewrite task IDs in input order after all requests succeed
    with open(task_file, "w") as f:
        for row_index in sorted(task_ids_by_row):
            f.write(f"{task_ids_by_row[row_index]}\n")

    # rewrite options file with new columns for
    # task id, creator, and updated output basenames
    options_out_file = f"{out}_options.tsv"
    with open(options_out_file, "w") as f:
        for line in out_lines:
            f.write(f"{line}\n")


if __name__ == "__main__":
    create_task_script()
