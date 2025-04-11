import click
from pathlib import Path
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--output_basename", help="output_basename")
@click.option("--alt_filter_pattern", help="alt_filter_pattern")
@click.option("--input_vcf", help="Input vcf to filter, sort, and index")
@click.option("--profile", help="Profile to use for api", default="cavatica")
@click.option("--task_file", help="File to write task ids to", default="task_ids.txt")
@click.option("--override_file", help="File to override input options", default=None)
@click.option("--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url")
@click.option("--app", help="App name, appid field on Cavaita app page")
def create_task(
	output_basename,
	alt_filter_pattern,
	input_vcf,
	profile,
	task_file,
	override_file,
	project,
	app,
):
	api = hf.parse_config(profile)
	task_ids = []

	if override_file:
		with open(override_file, "r") as f:
			line_num = 0
			overrides = []
			for line in f:
				if line_num == 0:
					overrides = line.strip().split("\t")
				else:
					line_vals = line.strip().split("\t")
					if "output_basename" in overrides:
						output_basename = line_vals[overrides.index("output_basename")]
					if "alt_filter_pattern" in overrides:
						alt_filter_pattern = line_vals[overrides.index("alt_filter_pattern")]
					if "input_vcf" in overrides:
						input_vcf = line_vals[overrides.index("input_vcf")]
					new_task = api.tasks.create(
						name="filter_and_sort_vcf",
						project=project,
						app=app,
						inputs = {
							"output_basename": output_basename,
							"alt_filter_pattern": alt_filter_pattern,
							"input_vcf": hf.get_file_obj(api, project, input_vcf),
						}
					)
					print(new_task.name, new_task.status, new_task.id)
					task_ids.append(new_task.id)
				line_num += 1
	else:
		new_task = api.tasks.create(
			name="filter_and_sort_vcf",
			project=project,
			app=app,
			inputs = {
				"output_basename": output_basename,
				"alt_filter_pattern": alt_filter_pattern,
				"input_vcf": hf.get_file_obj(api, project, input_vcf),
			},
		)
		print(new_task.name, new_task.status, new_task.id)
		task_ids.append(new_task.id)

	with open(task_file, "w") as f:
		for task_id in task_ids:
			f.write(f"{task_id}\n")

if __name__ == "__main__":
	create_task()
