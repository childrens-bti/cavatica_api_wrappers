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

## Other Scripts Usages

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