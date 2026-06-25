"""Use REST API to get task json file"""

import click
import requests
import gzip
import json
import configparser
from pathlib import Path
from tqdm import tqdm

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


def remove_metadata(obj):
    """
    Recursively remove the 'metadata' key from a dictionary or list of dictionaries.
    Inputs:
    - obj: a dictionary or list of dictionaries
    Returns:
    - None (the input object is modified in place)
    """
    if isinstance(obj, dict):
        obj.pop("metadata", None)
        for key in obj:
            remove_metadata(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            remove_metadata(item)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--task",
    required=False,
    help="Task id",
)
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
@click.option("--file", required=False, help="File with list of tasks to get info for.")
def get_task_json(profile, task, file):
    """Get the task json file for a given task.
    Or use the bulk action, but idk if that will work."""

    url, token = parse_config(profile)

    tasks = []

    # just try the bulk one and see what happens
    header = {
        "X-SBG-Auth-Token": f"{token}",
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    task_url = f"{url}/bulk/tasks/get"

    if task:
        tasks.append(task)
    if file:
        with open(file, "r") as f:
            tasks = [line.strip() for line in f]
    if not task and not file:
        print("Please provide either a task id or a file with task ids.")
        return None

    # split tasks into smaller groups for bulk request
    chunk_size = 100 # maximum set by SBG API
    chunks = [tasks[i : i + chunk_size] for i in range(0, len(tasks), chunk_size)]

    for chunk in tqdm(chunks, desc="Processing bulk tasks"):

        data = {"task_ids": chunk}
        data = json.dumps(data)

        # store chunk_number has 4 digits
        chunk_number = str(chunks.index(chunk)).zfill(4)

        response = requests.post(task_url, headers=header, data=data)
        if response.status_code == 200:
            # convert response to jsonl and save to file
            task_jsons = response.json()

            # remove metadata in any and all sub-keys
            # we might want to make this an option...
            #remove_metadata(task_jsons)

            out_file = f"task_jsons_{chunk_number}.jsonl.gz"
            with gzip.open(out_file, "wt", encoding="utf-8") as f:
                for task_json in task_jsons["items"]:
                    f.write(json.dumps(task_json) + "\n")
            
        else:
            print(f"Error: {response.status_code} - {response.text}")

    return None


if __name__ == "__main__":
    get_task_json()
