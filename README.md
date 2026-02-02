<p align="left">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

# Cavatica API Wrapper Scripts

This repository contains Python wrapper scripts using the [Seven Bridges Python api](https://github.com/sbg/sevenbridges-python).

[Sevenbridges API docs](https://docs.sevenbridges.com/page/api)

## Installing and using this repo.

To use the scripts contained within this repo:
1. Clone this repo locally
2. Create config file (see below)
3. Install required Python libraries
```python
pip install -r requirements.txt
```

### Config file

Copied from https://github.com/sbg/sevenbridges-python

The $HOME/.sevenbridges/credentials file has a simple .ini file format, for example:

    [default]
    api_endpoint = https://api.sbgenomics.com/v2
    auth_token = <TOKEN_HERE>

    [cgc]
    api_endpoint = https://cgc-api.sbgenomics.com/v2
    auth_token = <TOKEN_HERE>

    [cavatica]
    api_endpoint = https://cavatica-api.sbgenomics.com/v2
    auth_token = <TOKEN_HERE>

## Creating tasks from CWL workflows

Warning: this is very experimental and created tasks should be manually veririfed before using!

The `create_task_from_wf_cwl.py` script parses a CWL workflow and a tsv file with workflow inputs and creates tasks runing the parsed workflow in a project. The input file is described below. When the script is run, it will create draft tasks at the endpoint provided by your profile and will output a file containing the task ids of the created draft tasks. One task will be created for each line in the workflow inputs file. However, it won't load the workflow or any data needed to the project. This must be done separately.

### Generating Tasks

1. Create the project the workflow will be run in
1. Add the workflow to the project
1. Copy any reference and data files into the project
1. Clone the repo with the input workflow
1. Checkout the same github version of the workflow that matches the workflow in the project
1. Add inputs to the input tsv file
1. Run the script

### Script usage

To get a full list of inputs, run:
```bash
python scripts/create_task_from_wf_cwl.py -h
Usage: create_task_from_wf_cwl.py [OPTIONS]

  Create a draft task from a workflow cwl and file with task options.

Options:
  --profile TEXT            Profile to use from credentials file  [default:
                            cavatica]
  --project TEXT            Project the app is in, first two '/'s after 'u/'
                            in Cavatica url
  --app TEXT                App name, appid field on Cavaita app page
  -w, --workflow_file PATH  Path to workflow file
  --out TEXT                Output file
  --skip_name_check         Skip checking if app name and workflow file name
                            match
  --options_file PATH       Path to options file
  -h, --help                Show this message and exit.
```

#### The Options File

The options file is a tsv file with column names corresponding to workflow inputs. If an input is found in the options file, the values in that column will be used when creating draft tasks and will override any default or suggested values for that input. For example, if a workflow has an input `reference_fasta`, the values listed in the `reference_fasta` column in the input file will be used and the default value in the workflow will not.

Example options file
```bash
$ cat override.txt
vcf_file    output_basename
BS_1234.vcf BS_1234_example_workflow_run
BS_9876.vcf BS_9876_example_workflow_run
```

## Launching draft tasks

The Sevenbridges API separates creating tasks from launching them. Tasks are first created as drafts allowing for you to inspect them before running. The `run_tasks.py` script launches draft tasks using the draft task id or a file containing a list of task ids.

```bash
$ python run_tasks.py -h
Usage: run_tasks.py [OPTIONS]

  Launch a single task using the task id or launch multiple tasks getting the
  task ids from input file. Task file is a file with task ids one per line.
  This will only launch draft tasks and cannot create tasks.

Options:
  --task_file TEXT  File with task ids
  --task_id TEXT    Task id
  --profile TEXT    Profile to use from credentials file  [default: cavatica]
  --run             Run the task
  -h, --help        Show this message and exit.
```

## Adding metadata from manifest file

To add metadata to a file or list of files from a manifest, you will need a manifest file based on the templates found in the [manifest template repo](https://github.com/childrens-bti/manifest-template), the Cavatica project with files to add metadata to, and optionally as list of task ids that generated those files. The script will generate a metadata manifest that then must be uploaded to Cavatica to update the metadata.

### Steps to Add Metadata
1. Optionally create a file with task ids.
1. Run script to generate the metadata manifest
1. Navigate to the project page on Cavatica, click the `Files` tab
1. Click the 3 dots and select `Edit metadata with manifest
1. Navigate to and upload the metadata manifest file you just created

```bash
python scripts/add_metadata.py
Usage: add_metatdata.py [OPTIONS]

  Add metadata to files on Cavatica

Options:
  --profile TEXT          Profile to use from credentials file  [default:
                          cavatica]
  --project TEXT          Project ID
  --task_file TEXT        File with task ids
  -m, --manifest TEXT     Input Manifest file
  -o, --output_file TEXT  Output filename
  --debug                 Print some debug messages
  -h, --help              Show this message and exit.
```

0## Other Scripts Usages

Most scripts in this repo are simple and provide usage and inputs by running them with the -h option.

```bash
python scripts/{script} -h
```

For example:
```bash
python scripts/run_tasks.py
Usage: run_tasks.py [OPTIONS]

  Launch a single task using the task id or launch multiple tasks getting the
  task ids from input file. Task file is a file with task ids one per line.
  This will only launch draft tasks and cannot create tasks.

Options:
  --task_file TEXT  File with task ids
  --task_id TEXT    Task id
  --profile TEXT    Profile to use from credentials file  [default: cavatica]
  --run             Run the task
  -h, --help        Show this message and exit.
```

## ***DEPRECATED*** Creating API wrapper from CWL workflows

Warning: this is very experimental and should be manually verified before using!

The `create_task_script_from_wf_cwl.py` script parses a CWL workflow and creates a python script that uses the Sevenbridges API to create draft tasks. The generated script will have command line arguments for each workflow input, the project the workflow is uploaded to, the workflow app id in the project, and an option for a "override file" which is described below. When the generated script is run, it will create draft tasks at the endpoint provided by your profile and will output a file containing the task ids of the created draft tasks. Neither the `create_task_script_from_wf_cwl.py` script nor the scripts that it generates will load the workflow to the project. That must be done separately.

### Generating a Task Creation Script

1. Clone the repo with the input workflow
2. Run the generation script
```bash
$ python create_task_script_from_wf_cwl.py -w {workflow_path} > {generated_script}.py
```
3. If the script will be added to a repo for later use, it is strongly recommended to format the script using [black](https://github.com/psf/black).

### Using the generated script to create draft task(s)

1. Ensure the workflow and any input files exist within the project you will be running the workflow in.
2. Copy the app id from the project -> apps -> workflow page.
3. (Optional) create the override file.
4. Run the generated script. If the workflow has default values, those will be used when creating the tasks.
```bash
$ python {generated_script}.py --project {project} --app {appid} --task_file {task_file} {any additional workflow arguments and / or override file}
```

To get a full list of inputs, run:
```bash
$ python {generated_script}.py --help
```

#### The Override File

The override file is a tsv file with column names corresponding to workflow inputs. If an input is found in the override file, the values in that column will be used when creating draft tasks and will override the command line argument. For example, if a workflow has an input `vcf_file`, the values listed in the `vcf_file` column in the override file will be used and the command line argument `--vcf_file` will be ignored.


Example override file
```bash
$ cat override.txt
vcf_file    output_basename
BS_1234.vcf BS_1234_example_workflow_run
BS_9876.vcf BS_9876_example_workflow_run
```

## Launching draft tasks

The Sevenbridges API separates creating tasks from launching them. Tasks are first created as drafts allowing for you to inspect them before running. The `run_tasks.py` script launches draft tasks using the draft task id or a file containing a list of task ids. The script will launch a limited number of tasks, wait for those tasks to finsih, output the succesful task ids to an output file and failed tasks to a different file, then launch the next set of tasks. This script should be run on a system that will allow the script to be active the entire time tasks are running. If a batch of tasks does not finish after a set amount of time, this script will stop running and you will have to manually inspect these tasks and determine if they need to be aborted or not.

```bash
$ python run_tasks.py -h
Usage: run_tasks.py [OPTIONS]

  Launch a single task using the task id or launch multiple tasks getting the
  task ids from input file. Task file is a file with task ids one per line.
  This will only launch draft tasks and cannot create tasks.

Options:
  --task_file TEXT        File with task ids
  --task_id TEXT          Task id
  --profile TEXT          Profile to use from credentials file  [default:
                          cavatica]
  --limit INTEGER         Limit number of tasks to run at once, set to -1 to
                          run all task (not recommended)  [default: 50]
  --wait INTEGER          Time in minutes to wait between checking task status
                          [default: 60]
  --max_checks INTEGER    Maximum number of status checks to perform
                          [default: 12]
  --output_basename TEXT  Base name for output files  [default: task_status]
  -h, --help              Show this message and exit.
```

## Export Files from Cavatica

To export files, you will need a list of file ids on Cavatica, the name of the volume on Cavatica, and permission within Cavatica to export to that volume.

Note, Cavatica calls AWS buckets "volumes" rather than buckets and enforces shorter limits on volume namees. The volume name in Cavatica will not match the bucket name in AWS. You will need to look at the volumes you have access to at https://cavatica.sbgenomics.com/v

Exporting can only be done once, cannot be undone, and moving an exported file on AWS will mean the file is no longer useable on Cavatica. Slow down, take your time.

There are at least three ways to get file ids from Cavatica.
1. Manually from the url of the file.
1. Using the `get_files_by_task.py` script (most common)
1. Using the `find_all_exportable.py` script

The `export_file_by_id.py` script will export files from Cavatica. Authentication with AWS is handled through Cavatica, so you won't need any additional configuration.

** WARNING ** before running any export commands, have the command be reviewed by someone else to ensure the data are being exported to the correct bucket.

```bash
python scripts/export_file_by_id.py
Usage: export_file_by_id.py [OPTIONS]

  Take a task or a list of tasks and export the output data to an AWS bucket.
  All files will go to the same bucket/location.

Options:
  --file_ids TEXT  File with file ids  [required]
  --volume TEXT    username/volume_name of volume to export to.  [required]
  --profile TEXT   Profile to use from credentials file  [default: cavatica]
  --location TEXT  Bucket prefix to export data to (for example:
                   volume/folder/sub-folder)  [default: harmonized; required]
  --run            Run the export job
  --debug          Print some debug messages
  -h, --help       Show this message and exit.
```

### Getting file ids using `get_files_by_task.py`

The `get_files_by_task.py` script takes a file with a list of task ids such as ones created by the `run_tasks.py` script above. The output of this script is two tab separated columns file name and file id. You only need the second column for exporting.

```bash
python scripts/get_files_by_task.py
Usage: get_files_by_task.py [OPTIONS]

  Take a task or a list of tasks and find all output files.

Options:
  --task_file TEXT  File with task ids
  --task_id TEXT    Task id
  --profile TEXT    Profile to use from credentials file  [default: cavatica]
  --debug           Print some debug messages
  -h, --help        Show this message and exit
```

### Getting file ids using `find_all_exportable.py`

The `find_all_exportable.py` script will scan an input project for all files that haven't been exported. One current limitation of the Cavatica API is that files from DRS appear as if they exist only on Cavatica like non-exported files even though they are not exportable. These will have to be manually removed from the output. The output of this script is three tab separated columns: file name, file id, and created date.

```bash
python scripts/find_all_exportable.py
Usage: find_all_exportable.py [OPTIONS]

  Find a file in a project

Options:
  --project TEXT  Project ID
  --profile TEXT  Profile to use from credentials file  [default: cavatica]
  -h, --help      Show this message and exit
```

## Running Unit tests

```bash
python -m unittest discover -s scripts
```
