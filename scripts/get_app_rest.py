"""Get app info from REST api"""

import click
import requests
import json
import configparser
from pathlib import Path

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def parse_config(profile):
    """
    Parse the config file and return the api object.
    """
    home = Path.home()
    config = configparser.ConfigParser()
    config.read(home / ".sevenbridges/credentials")
    url = config[profile]["api_endpoint"]
    token = config[profile]["auth_token"]
    return [url, token]


def get_pattern(source, steps):
    """
    Get the glob pattern for an output source.
     """
    ret_source = "NA"
    ret_pattern = "NA"
    sources = []
    patterns = []

    if type(source) is list:
        sources = source
    else:
        sources = [source]
    for my_source in sources:
        step_id, output = my_source.split("/")
        #print(f"Looking for step {step_id} and output {output}")
        for step in steps:
            if step["id"] == step_id:
                pattern = "unable to find pattern"
                for out in step["run"]["outputs"]:
                    #print(out)
                    if out["id"] == output:
                        if "outputBinding" in out:
                            if "glob" in out["outputBinding"]:
                                pattern = out["outputBinding"]["glob"]
                            elif "outputEval" in out["outputBinding"]:
                                pattern = out["outputBinding"]["outputEval"]
                        elif "outputSource" in out:
                            #print(f"Recursively looking for pattern for source {out['outputSource']}")
                            sub_source, pattern = get_pattern(out["outputSource"], step["run"]["steps"])
                        elif "type" in out and out["type"] == "stdout":
                            pattern = "stdout"
                            if "stdout" in step["run"]:
                                pattern = step["run"]["stdout"]
                        elif step["run"]["class"] == "ExpressionTool":
                            pattern = "expression tool output"
                patterns.append(pattern)
                break

    ret_source = ",".join(sources)
    ret_pattern = ",".join(patterns)
    #print(f"Got source {ret_source} and pattern {ret_pattern}")
    return [ret_source, ret_pattern]


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--app",
    required=False,
    help="App ID, e.g. project-owner/project-name/app-name or project-owner/project-name/app-name/revision.",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
@click.option("--file", required=False, help="File with list of apps to get info for.")
@click.option("--dump_file", help="File to dump full app info to, for debugging.")
def get_app(profile, app, file, dump_file):
    """Get app information from Seven Bridges."""

    # get token and url from credentials file
    url, token = parse_config(profile)

    apps = []

    if app:
        apps.append(app)
    if file:
        with open(file, "r") as f:
            for line in f:
                apps.append(line.strip())
    if not app and not file:
        print("Please provide either an app ID or a file with a list of app IDs.")
        return

    header = {
        "X-SBG-Auth-Token": f"{token}",
        "accept": "application/json",
    }

    print(
        "app\tproject\trevisionNotes\trepo\thash\tfile\tcopy_pulled\tinputs (name:type:default)\toutputs (name:type:source:pattern)"
    )

    for app in apps:
        app_url = f"{url}/apps/{app}"

        response = requests.get(app_url, headers=header)

        if response.status_code == 200:
            res = response.json()

            # dump the whole app info, for debugging
            if app and dump_file:
                with open(dump_file, "w") as f:
                    json.dump(res, f, indent=4)

            # parse output results
            note = res["raw"]["sbg:revisionNotes"]
            out_line = f"{res["id"]}\t{res["project"]}\t{repr(note)}"
            # parse note
            repo = "NA"
            hash = "NA"
            file_name = "NA"
            copy_pulled = "NA"
            if note is None:
                note = ""
            if note.startswith("Uploaded"):
                note_split = note.split("\n")
                for line in note_split:
                    # if we find repo, hash, or commit, remove "{name}: " and save
                    if line.startswith("repo:"):
                        repo = line.replace("repo: ", "").strip()
                    elif line.startswith("commit:"):
                        hash = line.replace("commit: ", "").strip()
                    elif line.startswith("file:"):
                        file_name = line.replace("file: ", "").strip()
            elif note.startswith("Copy"):
                copied_id = note.replace("Copy of ", "").strip()
                if copied_id in apps:
                    copy_pulled = True
                else:
                    copy_pulled = False
            out_line += f"\t{repo}\t{hash}\t{file_name}\t{copy_pulled}"
            # parse inputs
            inps = []
            for item in res["raw"]["inputs"]:
                default = None
                id = item["id"]
                if type(item["type"]) is str:
                    my_type = item["type"]
                else:
                    my_type = "array"
                if "default" in item:
                    default = item["default"]
                inps.append(f"{id}:{my_type}:{default}")
            out_line += f"\t{'|'.join(inps)}"
            # parse outputs
            outs = []
            for item in res["raw"]["outputs"]:
                #print(item)
                id = item["id"]
                if "type" in item:
                    if type(item["type"]) is str:
                        my_type = item["type"]
                    else:
                        my_type = "array"
                source = "NA"
                pattern = "NA"
                if "outputSource" in item:
                    # app is probably a workflow
                    source, pattern = get_pattern(item["outputSource"], res["raw"]["steps"])
                elif "outputBinding" in item:
                    # app is probably a task app 
                    pattern = item["outputBinding"]["glob"]
                if "\n" in pattern:
                    pattern = pattern.replace("\n", "\\n")
                outs.append(f"{id}:{my_type}:{source}:{pattern}")
            out_line += f"\t{'|'.join(outs)}"

            print(out_line)

        else:
            print(f"{app}\tFailed to get app. Status code: {response.status_code}")


if __name__ == "__main__":
    get_app()
