"""Create a draft task launch script from a workflow cwl"""

import click
import sys
import yaml
from pathlib import Path
from sevenbridges import Api
from helper_functions import helper_functions as hf


@click.command(no_args_is_help=True)
@click.option(
    "-w",
    "--workflow_file",
    type=click.Path(exists=True),
    help="Path to workflow file",
)
@click.option(
    "-p",
    "--project",
    help="Project the app is in, first two '/'s after 'u/' in Cavatica url",
)
@click.option(
    "-a",
    "--app",
    help="App name, appid field on Cavaita app page",
)
def create_task_script(workflow_file, project, app):
    """
    Create a draft task launch script from a template and workflow cwl.
    """

    # read cwl workflow file
    app_name = workflow_file.split("/")[-1].split(".")[0]
    file_inputs = []
    int_inputs = []
    int_keywords = ["ram", "mem", "cpu", "core"]
    options = []
    my_inputs = []
    opt_base = f"@click.option(\"--"
    with open(workflow_file, "r") as stream:
        try:
            workflow = yaml.safe_load(stream)
            inputs = workflow["inputs"]
            for input in inputs:
                if any(x in input.lower() for x in int_keywords):
                    int_inputs.append(input)
                option = None
                if isinstance(inputs[input], str):
                    option = f"{opt_base}{input}\", help=\"{input}\")"
                elif isinstance(inputs[input], dict):
                    has_help = False
                    option = f"{opt_base}{input}\""
                    for key in inputs[input]:
                        if key == "type":
                            if inputs[input][key] == "File":
                                file_inputs.append(input)
                        elif key == "doc":
                            option += f", help=\"{inputs[input][key]}\""
                            has_help = True
                        elif key == "default":
                            option += f", default=\"{inputs[input][key]}\""
                        elif key == "secondaryFiles":
                            continue
                        elif key == "sbg:suggestedValue":
                            if isinstance(inputs[input][key], str):
                                option += f", default=\"{inputs[input][key]}\""
                            elif isinstance(inputs[input][key], dict):
                                option += f", default=\"{inputs[input][key]["name"]}\""
                        else:
                            print(f"Unknown key in input {key}")
                            exit(1)
                    if not has_help:
                        option += f", help=\"{input}\""
                    option += ")"
                else:
                    print("Unknown input type")
                    exit(1)
                options.append(option)
                my_inputs.append(input)
        except yaml.YAMLError as exc:
            print(exc)
            exit(1)
    print("Done processing workflow inputs!", file=sys.stderr)

    app_inputs = my_inputs.copy()

    # add extra necessary stuff to inputs (profile, task ids output file, and override file):
    options.append("@click.option(\"--profile\", help=\"Profile to use for api\", default=\"cavatica\")")
    my_inputs.append("profile")
    options.append("@click.option(\"--task_file\", help=\"File to write task ids to\", default=\"task_ids.txt\")")
    my_inputs.append("task_file")
    options.append("@click.option(\"--override_file\", help=\"File to override input options\", default=None)")
    my_inputs.append("override_file")

    # create input override file options
    """
    Override file is a tsv file with input names.
    they will be used for creating multiple tasks and will override the options
    provided to the cli"
    """

    # print output script
    
    # imports
    print("import click")
    print("from pathlib import Path")
    print("from helper_functions import helper_functions as hf\n")
    print("@click.command(no_args_is_help=True)")

    # command line args
    print("\n".join(options))

    # actual function and options
    print(f"def create_task(")
    for inp in my_inputs:
        print(f"\t{inp},")
    print(f"):")

    # get project and app from input
    print(f"\tproject = \"{project}\"")
    print(f"\tapp = \"{app}\"")

    # get api from helper functions reading config file
    print("\tapi = hf.parse_config(profile)")
    
    # set up calling api
    print("\ttask_ids = []")

    # read override file
    print("\n\tif override_file:")
    print("\t\tprint(\"Skipping override file, for now!\")")
    print("\t\twith open(override_file, \"r\") as f:")
    print("\t\t\tline_num = 0")
    print("\t\t\toverrides = []")
    print("\t\t\tfor line in f:")
    print("\t\t\t\tif line_num == 0:")
    print("\t\t\t\t\toverrides = line.strip().split(\"\\t\")")
    print("\t\t\t\telse:")
    print("\t\t\t\t\tline_vals = line.strip().split(\"\\t\")")

    # figure out overrides
    for inp in app_inputs:
        print(f"\t\t\t\tif \"{inp}\" in overrides:")
        print(f"\t\t\t\t\t{inp} = line_vals[overrides.index(\"{inp}\")]")
    
    # write api call
    print("\t\t\t\tnew_task = api.tasks.create(")
    print(f"\t\t\t\t\tname = \"{app_name}\",")
    print(f"\t\t\t\t\tproject = {project},")
    print(f"\t\t\t\t\tapp = {app},")
    print("\t\t\t\t\tinputs = {")
    for inp in app_inputs:
        if inp in file_inputs:
            print(f"\t\t\t\t\t\t\"{inp}\": hf.get_file_obj(api, project, {inp}),")
        elif inp in int_inputs:
            print(f"\t\t\t\t\t\t\"{inp}\": int({inp}),")
        else:
            print(f"\t\t\t\t\t\t\"{inp}\": {inp},")
    print("\t\t\t\t\t}")
    print("\t\t\t\t)")
    print("\t\t\ttask_ids.append(new_task.id)")

    # function call
    print("\telse:")
    print(f"\t\tnew_task = api.tasks.create(")
    print(f"\t\t\tname = \"{app_name}\",")
    print(f"\t\t\tproject = {project},")
    print(f"\t\t\tapp = {app},")
    print("\t\t\tinputs = {")
    for inp in app_inputs:
        if inp in file_inputs:
            print(f"\t\t\t\t\"{inp}\": hf.get_file_obj(api, project, {inp}),")
        elif inp in int_inputs:
            print(f"\t\t\t\t\"{inp}\": int({inp}),")
        else:
            print(f"\t\t\t\t\"{inp}\": {inp},")
    print("\t\t\t},")
    print("\t\t)")
    print("\t\ttask_ids.append(new_task.id)")

    # write task ids to file
    print("\n\twith open(task_file, \"w\") as f:")
    print("\t\tfor task_id in task_ids:")
    print("\t\t\tf.write(f\"{task_id}\\n\")")

    # bottom of script
    print("\nif __name__ == \"__main__\":")
    print("\tcreate_task()")

if __name__ == "__main__":
    create_task_script()