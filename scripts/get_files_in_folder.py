"""Get the file ids of output files from a list of tasks."""

import configparser
import json
import sys
from pathlib import Path

import click
import requests
from sevenbridges.errors import NotFound

from helper_functions import helper_functions as hf

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


def get_regular_files(api, initial_files, debug=False):
    """
    Get the file ids of output files from a list of tasks.
    Inputs:
    - api object
    - list of file objects
    Returns:
    - list of file objects
    """
    return list(iter_regular_files(api, initial_files, debug))


def iter_regular_files(api, initial_files, debug=False):
    """Yield regular files while carrying each folder's path through traversal."""
    yielded_ids = set()

    for file_id in initial_files:
        try:
            file_obj = api.files.get(id=file_id)
        except NotFound:
            print(f"Can't find {file_id}, file doesn't exist", file=sys.stderr)
            continue

        if not file_obj.is_folder():
            if file_obj.id not in yielded_ids:
                yielded_ids.add(file_obj.id)
                yield file_obj

            for secondary in file_obj.secondary_files or []:
                secondary_id = getattr(secondary, "id", secondary)
                if secondary_id in yielded_ids:
                    continue
                try:
                    secondary_obj = api.files.get(id=secondary_id)
                except NotFound:
                    print(
                        f"Can't find {secondary_id}, file doesn't exist",
                        file=sys.stderr,
                    )
                    continue
                yielded_ids.add(secondary_obj.id)
                yield secondary_obj
            continue

        print(f"Getting files in {file_obj.name}", file=sys.stderr)
        folders_to_visit = [(file_obj, file_obj.name)]
        files_processed = 0
        files_found = 0

        while folders_to_visit:
            folder, folder_path = folders_to_visit.pop()
            offset = 0

            while True:
                page = folder.list_files(limit=hf.LIMIT, offset=offset)
                received = len(page)
                if received == 0:
                    break

                for child in page:
                    files_processed += 1
                    child_path = f"{folder_path}/{child.name}"
                    if child.is_folder():
                        folders_to_visit.append((child, child_path))
                    elif child.id not in yielded_ids:
                        child.name = child_path
                        yielded_ids.add(child.id)
                        files_found += 1
                        yield child

                    if debug and files_processed % 1000 == 0:
                        print(
                            f"Processed {files_processed} entries; "
                            f"found {files_found} files",
                            file=sys.stderr,
                        )

                offset += received
                if offset >= page.total:
                    break

        print(f"Found {files_found} files", file=sys.stderr)


@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--project", help="Project ID")
@click.option(
    "--profile",
    help="Profile to use from credentials file",
    default="turbo",
    show_default=True,
)
@click.option(
    "--blacklist",
    help="Comma separated files with list of file ids to ignore",
    default=None,
)
@click.option("--debug", help="Print some debug messages", is_flag=True, default=False)
def get_folder_files(profile, project, debug, blacklist):
    """
    Get files at the top level of a project, then get files in those folders.
    This should only be used as a last resort.
    """
    # read config file
    api = hf.parse_config(profile)
    project = hf.parse_project(project)
    url, token = parse_config(profile)
    header = {
        "X-SBG-Auth-Token": f"{token}",
        "accept": "application/json",
    }

    blacklist_files = set(blacklist.split(",")) if blacklist else set()
    files = []

    file_url = f"{url}/projects/{project}/files?offset=0&limit=50"
    session = requests.Session()
    session.headers.update(header)
    response = session.get(file_url)
    if response.status_code != 200:
        print(f"Error getting files from project {project}: {response.text}")
        exit(1)
    else:
        res = response.json()
        if debug:
            with open("files_in_project.json", "w") as f:
                json.dump(res, f, indent=4)
        files = res["items"]
        while res["links"] and res["links"][0]["rel"] == "next":
            file_url = f"{res["links"][0]["href"]}"
            if debug:
                print(file_url, file=sys.stderr)
            response = session.get(file_url)
            if response.status_code != 200:
                print(f"Error getting files from project {project}: {response.text}")
                exit(1)
            else:
                res = response.json()
                files.extend(res["items"])

    files_found = 0
    print("file_name\tfile_id")
    for file in files:
        name = file["name"]
        id = file["id"]
        if name not in blacklist_files:
            print(f"{name}\t{id}", file=sys.stderr)
            for regular_file in iter_regular_files(api, [id], debug):
                print(f"{regular_file.name}\t{regular_file.id}")
                files_found += 1

    print(f"Found {files_found} files to display", file=sys.stderr)
    if files_found == 0:
        print("No files found in input folders")


if __name__ == "__main__":
    get_folder_files()
