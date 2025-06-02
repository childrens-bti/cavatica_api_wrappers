import click
from pathlib import Path
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--vep_vcf", help="VCF file (with associated index) to be annotated")
@click.option("--buildver", help="Genome reference build version", default="hg38")
@click.option("--output_basename", help="String that will be used in the output filenames. Be sure to be consistent with this as InterVar will use this too")
@click.option("--annovar_db", help="Annovar Database with at minimum required resources to InterVar", default="annovar_humandb_hg38_intervar.tgz")
@click.option("--annovar_db_str", help="Name of dir created when annovar db is un-tarred", default="annovar_humandb_hg38_intervar")
@click.option("--annovar_protocol", help="csv string of databases within `annovar_db` cache to run", default="refGene,esp6500siv2_all,1000g2015aug_all,avsnp147,dbnsfp42a,clinvar_20210501,gnomad_genome,dbscsnv11,rmsk,ensGene,knownGene")
@click.option("--annovar_operation", help="csv string of how to treat each listed protocol", default="g,f,f,f,f,f,f,f,r,g,g")
@click.option("--annovar_nastring", help="character used to represent missing values", default=".")
@click.option("--annovar_otherinfo", help="print out otherinfo (information after fifth column in queryfile)", default="True")
@click.option("--annovar_threads", help="Num threads to use to process filter inputs", default="8")
@click.option("--annovar_ram", help="Memory to run tool. Sometimes need more", default="32")
@click.option("--annovar_vcfinput", help="Annotate vcf and generate output file as vcf", default="True")
@click.option("--bcftools_strip_for_intervar", help="csv string of columns to strip if needed to avoid conflict/improve performance of a tool, i.e INFO/CSQ", default="^INFO/DP")
@click.option("--bcftools_strip_for_vep", help="csv string of columns to strip if needed to avoid conflict/improve performance of a tool, i.e INFO/CSQ")
@click.option("--bcftools_strip_for_annovar", help="csv string of columns to strip if needed to avoid conflict/improve performance of a tool, i.e INFO/CLNSIG")
@click.option("--bcftools_annot_columns", help="csv string of columns from annotation to port into the input vcf", default="INFO/ALLELEID,INFO/CLNDN,INFO/CLNDNINCL,INFO/CLNDISDB,INFO/CLNDISDBINCL,INFO/CLNHGVS,INFO/CLNREVSTAT,INFO/CLNSIG,INFO/CLNSIGCONF,INFO/CLNSIGINCL,INFO/CLNVC,INFO/CLNVCSO,INFO/CLNVI")
@click.option("--annotation_vcf", help="additional bgzipped annotation vcf file")
@click.option("--intervar_db", help="InterVar Database from git repo + mim_genes.txt", default="intervardb_2021-08.tar.gz")
@click.option("--intervar_db_str", help="Name of dir created when intervar db is un-tarred", default="intervardb")
@click.option("--intervar_ram", help="Min ram needed for task in GB", default="32")
@click.option("--autopvs1_db", help="git repo files plus a user-provided fasta reference", default="autoPVS1_references_sym_updated.tar.gz")
@click.option("--autopvs1_db_str", help="Name of dir created when annovar db is un-tarred", default="data")
@click.option("--profile", help="Profile to use for api", default="cavatica")
@click.option("--task_file", help="File to write task ids to", default="task_ids.txt")
@click.option("--override_file", help="File to override input options", default=None)
@click.option("--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url")
@click.option("--app", help="App name, appid field on Cavaita app page")
def create_task(
	vep_vcf,
	buildver,
	output_basename,
	annovar_db,
	annovar_db_str,
	annovar_protocol,
	annovar_operation,
	annovar_nastring,
	annovar_otherinfo,
	annovar_threads,
	annovar_ram,
	annovar_vcfinput,
	bcftools_strip_for_intervar,
	bcftools_strip_for_vep,
	bcftools_strip_for_annovar,
	bcftools_annot_columns,
	annotation_vcf,
	intervar_db,
	intervar_db_str,
	intervar_ram,
	autopvs1_db,
	autopvs1_db_str,
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
					if "vep_vcf" in overrides:
						vep_vcf = line_vals[overrides.index("vep_vcf")]
					if "buildver" in overrides:
						buildver = line_vals[overrides.index("buildver")]
					if "output_basename" in overrides:
						output_basename = line_vals[overrides.index("output_basename")]
					if "annovar_db" in overrides:
						annovar_db = line_vals[overrides.index("annovar_db")]
					if "annovar_db_str" in overrides:
						annovar_db_str = line_vals[overrides.index("annovar_db_str")]
					if "annovar_protocol" in overrides:
						annovar_protocol = line_vals[overrides.index("annovar_protocol")]
					if "annovar_operation" in overrides:
						annovar_operation = line_vals[overrides.index("annovar_operation")]
					if "annovar_nastring" in overrides:
						annovar_nastring = line_vals[overrides.index("annovar_nastring")]
					if "annovar_otherinfo" in overrides:
						annovar_otherinfo = line_vals[overrides.index("annovar_otherinfo")]
					if "annovar_threads" in overrides:
						annovar_threads = line_vals[overrides.index("annovar_threads")]
					if "annovar_ram" in overrides:
						annovar_ram = line_vals[overrides.index("annovar_ram")]
					if "annovar_vcfinput" in overrides:
						annovar_vcfinput = line_vals[overrides.index("annovar_vcfinput")]
					if "bcftools_strip_for_intervar" in overrides:
						bcftools_strip_for_intervar = line_vals[overrides.index("bcftools_strip_for_intervar")]
					if "bcftools_strip_for_vep" in overrides:
						bcftools_strip_for_vep = line_vals[overrides.index("bcftools_strip_for_vep")]
					if "bcftools_strip_for_annovar" in overrides:
						bcftools_strip_for_annovar = line_vals[overrides.index("bcftools_strip_for_annovar")]
					if "bcftools_annot_columns" in overrides:
						bcftools_annot_columns = line_vals[overrides.index("bcftools_annot_columns")]
					if "annotation_vcf" in overrides:
						annotation_vcf = line_vals[overrides.index("annotation_vcf")]
					if "intervar_db" in overrides:
						intervar_db = line_vals[overrides.index("intervar_db")]
					if "intervar_db_str" in overrides:
						intervar_db_str = line_vals[overrides.index("intervar_db_str")]
					if "intervar_ram" in overrides:
						intervar_ram = line_vals[overrides.index("intervar_ram")]
					if "autopvs1_db" in overrides:
						autopvs1_db = line_vals[overrides.index("autopvs1_db")]
					if "autopvs1_db_str" in overrides:
						autopvs1_db_str = line_vals[overrides.index("autopvs1_db_str")]
					new_task = api.tasks.create(
						name="d3b-diskin-pathogenicity-preprocess-wf",
						project=project,
						app=app,
						inputs = {
							"vep_vcf": hf.get_file_obj(api, project, vep_vcf),
							"buildver": buildver,
							"output_basename": output_basename,
							"annovar_db": hf.get_file_obj(api, project, annovar_db),
							"annovar_db_str": annovar_db_str,
							"annovar_protocol": annovar_protocol,
							"annovar_operation": annovar_operation,
							"annovar_nastring": annovar_nastring,
							"annovar_otherinfo": bool(annovar_otherinfo),
							"annovar_threads": annovar_threads,
							"annovar_ram": int(annovar_ram),
							"annovar_vcfinput": bool(annovar_vcfinput),
							"bcftools_strip_for_intervar": bcftools_strip_for_intervar,
							"bcftools_strip_for_vep": bcftools_strip_for_vep,
							"bcftools_strip_for_annovar": bcftools_strip_for_annovar,
							"bcftools_annot_columns": bcftools_annot_columns,
							"annotation_vcf": hf.get_file_obj(api, project, annotation_vcf),
							"intervar_db": hf.get_file_obj(api, project, intervar_db),
							"intervar_db_str": intervar_db_str,
							"intervar_ram": int(intervar_ram),
							"autopvs1_db": hf.get_file_obj(api, project, autopvs1_db),
							"autopvs1_db_str": autopvs1_db_str,
						}
					)
					print(new_task.name, new_task.status, new_task.id)
					task_ids.append(new_task.id)
				line_num += 1
	else:
		new_task = api.tasks.create(
			name="d3b-diskin-pathogenicity-preprocess-wf",
			project=project,
			app=app,
			inputs = {
				"vep_vcf": hf.get_file_obj(api, project, vep_vcf),
				"buildver": buildver,
				"output_basename": output_basename,
				"annovar_db": hf.get_file_obj(api, project, annovar_db),
				"annovar_db_str": annovar_db_str,
				"annovar_protocol": annovar_protocol,
				"annovar_operation": annovar_operation,
				"annovar_nastring": annovar_nastring,
				"annovar_otherinfo": bool(annovar_otherinfo), 
				"annovar_threads": annovar_threads,
				"annovar_ram": int(annovar_ram),
				"annovar_vcfinput": bool(annovar_vcfinput), 
				"bcftools_strip_for_intervar": bcftools_strip_for_intervar,
				"bcftools_strip_for_vep": bcftools_strip_for_vep,
				"bcftools_strip_for_annovar": bcftools_strip_for_annovar,
				"bcftools_annot_columns": bcftools_annot_columns,
				"annotation_vcf": hf.get_file_obj(api, project, annotation_vcf),
				"intervar_db": hf.get_file_obj(api, project, intervar_db),
				"intervar_db_str": intervar_db_str,
				"intervar_ram": int(intervar_ram),
				"autopvs1_db": hf.get_file_obj(api, project, autopvs1_db),
				"autopvs1_db_str": autopvs1_db_str,
			},
		)
		print(new_task.name, new_task.status, new_task.id)
		task_ids.append(new_task.id)

	with open(task_file, "w") as f:
		for task_id in task_ids:
			f.write(f"{task_id}\n")

if __name__ == "__main__":
	create_task()
