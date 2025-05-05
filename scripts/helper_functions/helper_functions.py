"""Helper functions for sbg python api"""

import configparser
from pathlib import Path
from sevenbridges import Api
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper

# set api limit for pagination
LIMIT = 50


def find_file_in_folder(folder, search_name, result_list=None):
    """
    Search for a file within a folder in a project.
    Inputs:
    - folder: folder object
    - search_name: file name to search for
    Returns:
    - result_list: list of all results from recursive query
    """

    if result_list is None:
        result_list = []

    for file in folder:
        if file.name == search_name:
            result_list.append(file)
        elif file.is_folder() == True:
            # get all files in the folder using pagination
            recieved = LIMIT
            new_folder = file.list_files(limit=LIMIT)
            find_file_in_folder(new_folder, search_name, result_list)
            while recieved < new_folder.total:
                find_file_in_folder(file.list_files(limit=LIMIT, offset=recieved), search_name, result_list)
                recieved += LIMIT
            
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

        # query project for all files using pagination
        recieved = LIMIT
        project_files = project_obj.get_files(limit=LIMIT)
        found_files = find_file_in_folder(project_files, file_name)
        while recieved < project_files.total:
            project_files = project_obj.get_files(limit=LIMIT, offset=recieved)
            found_files.extend(find_file_in_folder(project_files, file_name))
            recieved += LIMIT

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
        error_handlers=[rate_limit_sleeper, maintenance_sleeper]
    )

    return api
