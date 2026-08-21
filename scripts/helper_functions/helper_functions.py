"""Helper functions for sbg python api"""

import configparser
import sys
from pathlib import Path
from sevenbridges import Api
from sevenbridges.errors import SbgError
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper

# set api limit for pagination
LIMIT = 100


def get_all_files_folder(api, folder) -> list:
    """
    Get all files in a folder including in sub folders
    Inputs:
    - api: api obejct
    - folder: file object with is_folder() == True
    Returns:
    - list of file objects in the folder and subfolders
    """

    all_files = []

    if folder.is_folder() == False:
        raise ValueError(f"ERROR: File {folder.name} is not a folder")
    
    # get all of the files in a folder
    folder_files = folder.list_files(limit=LIMIT)
    all_files.extend(folder_files)
    received = LIMIT
    while received < folder_files.total:
        folder_files = folder.list_files(limit=LIMIT, offset=received)
        all_files.extend(folder_files)
        received += LIMIT

    # check if any of the files are a folder
    for file in all_files:
        if file.is_folder() == True:
            received = LIMIT
            folder_files = file.list_files(limit=LIMIT)
            all_files.extend(folder_files)
            while received < folder_files.total:
                folder_files = file.list_files(limit=LIMIT, offset=received)
                all_files.extend(folder_files)
                received += LIMIT

    return all_files


def get_all_files(api, project) -> list:
    """
    Get all files in a project including in folders
    Inputs:
    - api: api obejct
    - project: project name
    Returns:
    - list of file objects in the project and subfolders
    """
    all_files = []

    # get all files in the project
    project_obj = api.projects.get(id=project)

    # query project for all files using pagination
    project_files = project_obj.get_files(limit=LIMIT)
    all_files.extend(project_files)
    received = LIMIT
    while received < project_files.total:
        project_files = project_obj.get_files(limit=LIMIT, offset=received)
        all_files.extend(project_files)
        received += LIMIT

    # check if any of the files are a folder
    for file in all_files:
        if file.is_folder() == True:
            received = LIMIT
            folder_files = file.list_files(limit=LIMIT)
            all_files.extend(folder_files)
            while received < folder_files.total:
                folder_files = file.list_files(limit=LIMIT, offset=received)
                all_files.extend(folder_files)
                received += LIMIT

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
            received = LIMIT
            new_folder = file.list_files(limit=LIMIT)
            find_file_in_folder(new_folder, search_name, result_list)
            while received < new_folder.total:
                find_file_in_folder(
                    file.list_files(limit=LIMIT, offset=received),
                    search_name,
                    result_list,
                )
                received += LIMIT

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
    file_obj = None

    # first search for the file directly
    files = api.files.query(project=project, names=[file_name])
    if len(files) == 0:
        found_files = []

        # search for the file in the project

        # get all files in the project
        project_obj = api.projects.get(id=project)

        # query project for all files using pagination
        received = LIMIT
        project_files = project_obj.get_files(limit=LIMIT)
        found_files = find_file_in_folder(project_files, file_name)
        while received < project_files.total:
            project_files = project_obj.get_files(limit=LIMIT, offset=received)
            found_files.extend(find_file_in_folder(project_files, file_name))
            received += LIMIT

        if len(found_files) == 0:
            raise FileNotFoundError(
                f"ERROR: File {file_name} not found in project {project}"
            )
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
    received = LIMIT
    project_tasks = api.tasks.query(project=project, limit=LIMIT)
    tasks.extend(project_tasks)
    while received < project_tasks.total:
        project_tasks = api.tasks.query(project=project, limit=LIMIT, offset=received)
        tasks.extend(project_tasks)
        received += LIMIT

    return tasks


def query_tasks(api, **kwargs):
    """
    Query tasks available to user with kwargs as query parameters
    for example: project, status, created_from, etc.
    """
    tasks = []
    received = LIMIT
    project_tasks = api.tasks.query(limit=LIMIT, **kwargs)
    tasks.extend(project_tasks)
    while received < project_tasks.total:
        project_tasks = api.tasks.query(limit=LIMIT, offset=received, **kwargs)
        tasks.extend(project_tasks)
        received += LIMIT

    return tasks


def _query_projects_resilient(api, offset, limit):
    """
    Fetch one page of api.projects.query(), skipping any individual project
    the platform can't serialize instead of failing the whole page. Some
    projects 500 on the full-field expansion the SDK always requests (seen
    with cavatica/pnoc-dipg-pa-02) - bisect a failing page down to isolate
    and skip just the broken record(s).
    """
    try:
        return list(api.projects.query(limit=limit, offset=offset))
    except SbgError as e:
        if limit == 1:
            print(
                f"WARNING: skipping project at offset {offset} "
                f"(server error: {e.message})",
                file=sys.stderr,
            )
            return []
        mid = limit // 2
        return _query_projects_resilient(api, offset, mid) + _query_projects_resilient(
            api, offset + mid, limit - mid
        )


def get_all_projects(api):
    """
    Get all projects the user has access to. Projects the platform can't
    serialize are skipped with a warning (see _query_projects_resilient)
    rather than aborting the whole report.
    """
    total = api.projects.query(limit=1).total
    projects = []
    offset = 0
    while offset < total:
        projects.extend(_query_projects_resilient(api, offset, LIMIT))
        offset += LIMIT

    return projects


def get_all_billing(api):
    """
    Get all billing groups the user has access to.
    """
    billings = []
    received = LIMIT
    billing_page = api.billing_groups.query(limit=LIMIT)
    billings.extend(billing_page)
    while received < billing_page.total:
        billing_page = api.billing_groups.query(limit=LIMIT, offset=received)
        billings.extend(billing_page)
        received += LIMIT

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


def parse_project(project):
    """
    Parse the project id or url and return just the id
    """
    out_project = None

    # project can be None if a project is not required by a script
    if project is not None:

        project_split = project.split("/")
        if len(project_split) == 2:
            out_project = project_split[-2] + "/" + project_split[-1]
        elif len(project_split) > 2:
            # check if url contains "u/" which indicates the start of the project id
            if "u" in project_split:
                u_index = project_split.index("u")
                out_project = project_split[u_index + 1] + "/" + project_split[u_index + 2]
            else:
                raise ValueError(
                    f"ERROR: Project {project} is not in the correct format, please provide a project id in the format 'user/project' or a url containing 'u/' followed by the project id"
                )
        else:
            raise ValueError(
                f"ERROR: Project {project} is not in the correct format, please provide a project id in the format 'user/project' or a url containing 'u/' followed by the project id"
            )

    return out_project
