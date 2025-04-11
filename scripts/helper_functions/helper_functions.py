"""Helper functions for sbg python api"""

import configparser
from pathlib import Path
from sevenbridges import Api


def find_file_in_folder(folder, search_name, result_list=None):
    """
    Search for a file within a folder in a project.
    Inputs:
    - folder: folder object
    - search_name: file name to search for
    Returns:
    - file_obj: api file object
    """

    if result_list is None:
        result_list = []

    for file in folder:
        if file.name == search_name:
            result_list.append(file)
        elif file.is_folder() == True:
            find_file_in_folder(file.list_files(), search_name, result_list)
    return result_list


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
    print(f"Searching {project} for {file_name}")
    file_obj = None

    # first search for the file directly
    files = api.files.query(project=project, names=[file_name])
    if len(files) == 0:
        found_files = []
        print(
            f"File {file_name} not found in root dir of {project}, searching within folders"
        )
        # search for the file in the project

        # get all files in the project
        project_obj = api.projects.get(id=project)

        project_files = project_obj.get_files()
        found_files = find_file_in_folder(project_files, file_name)

        if len(found_files) == 0:
            print(f"ERROR: File {file_name} not found in project {project}")
            exit(1)
        elif len(found_files) > 1:
            print(
                f"ERROR: Multiple files found with name {file_name} in project {project}"
            )
            exit(1)
        else:
            file_obj = found_files[0]

    elif len(files) > 1:
        print(f"ERROR: Multiple files found with name {file_name} in project {project}")
        exit(1)
    else:
        file_obj = files[0]

    return file_obj


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
