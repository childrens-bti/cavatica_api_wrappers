"""Helper functions for sbg python api"""

import configparser
from pathlib import Path
from sevenbridges import Api
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper

# set api limit for pagination
LIMIT = 50


def get_all_files(api, project) -> list:
    """
    Get all files in a project including in folders
    Inputs:
    - api: api obejct
    - project: project name
    Returns:
    - 
    """
    all_files = []

    # get all files in the project
    project_obj = api.projects.get(id=project)

    # query project for all files using pagination
    recieved = LIMIT
    project_files = project_obj.get_files(limit=LIMIT)
    all_files.extend(project_files)
    while recieved < project_files.total:
        project_files = project_obj.get_files(limit=LIMIT, offset=recieved)
        all_files.extend(project_files)
        recieved += LIMIT

    # check if any of the files are a folder
    for file in all_files:
        if file.is_folder() == True:
            recieved = LIMIT
            folder_files = file.list_files(limit=LIMIT)
            all_files.extend(folder_files)
            while recieved < folder_files.total:
                folder_files = file.list_files(limit=LIMIT, offset=recieved)
                recieved += LIMIT

    return all_files


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
                find_file_in_folder(
                    file.list_files(limit=LIMIT, offset=recieved),
                    search_name,
                    result_list,
                )
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
            raise FileNotFoundError(f"ERROR: File {file_name} not found in project {project}")
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


def get_all_tasks(api, project):
    """
    Get all tasks in a project.
    """
    tasks = []
    recieved = LIMIT
    project_tasks = api.tasks.query(project=project, limit=LIMIT)
    tasks.extend(project_tasks)
    while recieved < project_tasks.total:
        project_tasks = api.tasks.query(project=project, limit=LIMIT, offset = recieved)
        tasks.extend(project_tasks)
        recieved += LIMIT

    return tasks


def get_all_projects(api):
    """
    Get all projects the user has access to.
    """
    print("Finding projects")
    projects = []
    recieved = LIMIT
    project_page = api.projects.query(limit=LIMIT)
    projects.extend(project_page)
    while recieved < project_page.total:
        print(f"Looking for more projects, found {recieved}")
        project_page = api.projects.query(limit=LIMIT, offset = recieved)
        projects.extend(project_page)
        recieved += LIMIT

    return projects


def get_all_billing(api):
    """
    Get all billing groups the user has access to.
    """
    print("Finding billing groups")
    billings = []
    recieved = LIMIT
    billing_page = api.billing_groups.query(limit=LIMIT)
    billings.extend(billing_page)
    while recieved < billing_page.total:
        print(f"Looking for more projects, found {recieved}")
        billing_page = api.billing_groups.query(limit=LIMIT, offset = recieved)
        billings.extend(billing_page)
        recieved += LIMIT

    return billings


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
        error_handlers=[rate_limit_sleeper, maintenance_sleeper],
    )

    return api


def bulk_export_files(api, files, volume, location, overwrite=True, copy_only=False):
    """
    Exports list of files to volume in bulk
    """

    chunk_size = 100  # Max legal bulk size for export is 100 items.
    final_responses = []

    def is_finished(response):
        return response in ["COMPLETED", "FAILED", "ABORTED"]

    def error_handling_after_completion(responses):
        errors = [
            s.resource.error.message for s in responses if s.resource.state == "FAILED"
        ]
        if errors:
            data = [
                s.resource.error if s.resource.state == "FAILED" else s.resource.result
                for s in responses
            ]
            raise Exception(
                "There were errors with bulk exporting.\n"
                + "\n".join([str(d) for d in data])
            )

    def error_handling_after_submission(responses):
        errors = [s.error.message for s in responses if not s.valid]
        if errors:
            data = [s for s in responses if not s.valid]

            raise Exception(
                "There were errors with bulk submission.\n"
                + "\n".join(
                    [
                        f"<Error: status={s.error.status}, code={s.error.code}>; "
                        f"{s.error.message}"
                        for s in data
                    ]
                )
            )

    # export files in batches of chunck_size files each
    for i in range(0, len(files), chunk_size):

        # setup list of dictionary with export requests
        exports = [
            {
                "file": f,
                "volume": volume,
                "location": location + "/" + f.name,
                "overwrite": overwrite,
            }
            for f in files[i : i + chunk_size]
        ]

        # initiate bulk export of batch and wait until finished
        responses = api.exports.bulk_submit(exports, copy_only=copy_only)

        # check for errors in bulk submission
        error_handling_after_submission(responses)

        # wait for bulk job to finish
        while not all(is_finished(s.resource.state) for s in responses):
            responses = api.exports.bulk_get([s.resource for s in responses])

        # check if each job finished successfully
        error_handling_after_completion(responses)

        final_responses.extend(responses)

        if len(final_responses) % 1000 == 0:
            print(f"Exported: {len(final_responses)} files")

    return final_responses
