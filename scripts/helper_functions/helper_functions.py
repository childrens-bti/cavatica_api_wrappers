"""Helper functions for sbg python api"""

import configparser
from pathlib import Path
from sevenbridges import Api


def get_file_obj(api, project, file_name) -> str:
    """
    Lookup the file id for a file in a project.
    Inputs:
    - api: api obejct
    - project: project name
    - file_name: file name to lookup
    Returns:
    - file_obj: api file object
    """
    print(f"Looking up file id for file: {file_name}")
    file_id = None
    files = api.files.query(project=project, names=[file_name])
    if len(files) == 0:
        print(f"ERROR: File {file_name} not found in project {project}")
        exit(1)
    elif len(files) > 1:
        print(f"ERROR: Multiple files found with name {file_name} in project {project}")
        exit(1)
    else:
        file_id = files[0].id

    return api.files.get(id=file_id)


def parse_config(profile):
    """
    Parse the config file and return the api object.
    """
    home = Path.home()
    config = configparser.ConfigParser()
    config.read(home / ".sevenbridges/credentials")
    api = Api(
        url=config[profile]["api_endpoint"],
        token=config[profile]["auth_token"],
    )

    return api
