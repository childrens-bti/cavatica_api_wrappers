import click
import datetime
import time
from pathlib import Path
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--input_bam_list", help="List of input BAM files")
@click.option("--input_pe_reads_list", help="List of input R1 paired end fastq reads")
@click.option("--input_pe_mates_list", help="List of input R2 paired end fastq reads")
@click.option("--input_pe_rgs_list", help="List of RG strings to use in PE processing")
@click.option("--input_se_reads_list", help="List of input singlie end fastq reads")
@click.option("--input_se_rgs_list", help="List of RG strings to use in SE processing")
@click.option("--reference_tar", help="Tar file containing a reference fasta and, optionally, its complete set of associated indexes (samtools, bwa, and picard)", default="Homo_sapiens_assembly38.tgz")
@click.option("--cram_reference", help="If aligning from cram, need to provided reference used to generate that cram")
@click.option("--biospecimen_name", help="String name of biospcimen")
@click.option("--output_basename", help="String to use as the base for output filenames")
@click.option("--dbsnp_vcf", help="dbSNP vcf file", default="Homo_sapiens_assembly38.dbsnp138.vcf")
@click.option("--dbsnp_idx", help="dbSNP vcf index file", default="Homo_sapiens_assembly38.dbsnp138.vcf.idx")
@click.option("--knownsites", help="List of files containing known polymorphic sites used to exclude regions around known polymorphisms from analysis")
@click.option("--knownsites_indexes", help="Corresponding indexes for the knownsites. File position in list must match with its corresponding VCF's position in the knownsites file list. For example, if the first file in the knownsites list is 1000G_omni2.5.hg38.vcf.gz then the first item in this list must be 1000G_omni2.5.hg38.vcf.gz.tbi. Optional, but will save time/cost on indexing.")
@click.option("--contamination_sites_bed", help=".bed file for markers used in this analysis,format(chr	pos-1	pos	refAllele	altAllele)", default="Homo_sapiens_assembly38.contam.bed")
@click.option("--contamination_sites_mu", help=".mu matrix file of genotype matrix", default="Homo_sapiens_assembly38.contam.mu")
@click.option("--contamination_sites_ud", help=".UD matrix file from SVD result of genotype matrix", default="Homo_sapiens_assembly38.contam.UD")
@click.option("--wgs_calling_interval_list", help="WGS interval list used to aid scattering Haplotype caller", default="wgs_calling_regions.hg38.interval_list")
@click.option("--wgs_coverage_interval_list", help="An interval list file that contains the positions to restrict the wgs metrics assessment", default="wgs_coverage_regions.hg38.interval_list")
@click.option("--wgs_evaluation_interval_list", help="Target intervals to restrict gvcf metric analysis (for VariantCallingMetrics)", default="wgs_evaluation_regions.hg38.interval_list")
@click.option("--wxs_bait_interval_list", help="An interval list file that contains the locations of the WXS baits used (for HsMetrics)")
@click.option("--wxs_target_interval_list", help="An interval list file that contains the locations of the WXS targets (for HsMetrics)")
@click.option("--run_bam_processing", help="BAM processing will be run. Requires: input_bam_list")
@click.option("--run_pe_reads_processing", help="PE reads processing will be run. Requires: input_pe_reads_list, input_pe_mates_list, input_pe_rgs_list")
@click.option("--run_se_reads_processing", help="SE reads processing will be run. Requires: input_se_reads_list, input_se_rgs_list")
@click.option("--run_hs_metrics", help="HsMetrics will be collected. Only recommended for WXS inputs. Requires: wxs_bait_interval_list, wxs_target_interval_list")
@click.option("--run_wgs_metrics", help="WgsMetrics will be collected. Only recommended for WGS inputs. Requires: wgs_coverage_interval_list")
@click.option("--run_agg_metrics", help="AlignmentSummaryMetrics, GcBiasMetrics, InsertSizeMetrics, QualityScoreDistribution, and SequencingArtifactMetrics will be collected. Recommended for both WXS and WGS inputs.")
@click.option("--run_sex_metrics", help="idxstats will be collected and X/Y ratios calculated")
@click.option("--run_gvcf_processing", help="gVCF will be generated. Requires: dbsnp_vcf, contamination_sites_bed, contamination_sites_mu, contamination_sites_ud, wgs_calling_interval_list, wgs_evaluation_interval_list")
@click.option("--cutadapt_r1_adapter", help="If read1 reads have an adapter, provide regular 3' adapter sequence here to remove it from read1")
@click.option("--cutadapt_r2_adapter", help="If read2 reads have an adapter, provide regular 3' adapter sequence here to remove it from read2")
@click.option("--cutadapt_min_len", help="If adapter trimming, discard reads/read-pairs where the read length is less than this value. Set to 0 to turn off")
@click.option("--cutadapt_quality_base", help="If adapter trimming, use this value as the base quality score. Defaults to 33 but very old reads might need this value set to 64")
@click.option("--cutadapt_quality_cutoff", help="If adapter trimming, remove bases from the 3'/5' that fail to meet this cutoff value. If you specify a single cutoff value, the 3' end of each read is trimmed. If you specify two cutoff values separated by a comma, the first value will be trimmed from the 5' and the second value will be trimmed from the 3'")
@click.option("--min_alignment_score", default="30", help="For BWA MEM, Don't output alignment with score lower than INT. This option only affects output.")
@click.option("--bamtofastq_cpu", help="CPUs to allocate to bamtofastq")
@click.option("--run_t1k", default="True", help="Set to false to disable T1k HLA typing")
@click.option("--hla_dna_ref_seqs", help="FASTA file containing the HLA allele reference sequences for DNA.", default="hla_v3.43.0_gencode_v39_dna_seq.fa")
@click.option("--hla_dna_gene_coords", help="FASTA file containing the coordinates of the HLA genes for DNA.", default="hla_v3.43.0_gencode_v39_dna_coord.fa")
@click.option("--t1k_abnormal_unmap_flag", help="Set if the flag in BAM for the unmapped read-pair is nonconcordant")
@click.option("--t1k_ram", help="GB of RAM to allocate to T1k.")
@click.option("--profile", help="Profile to use for api", default="cavatica")
@click.option("--task_file", help="File to write task ids to", default="task_ids.txt")
@click.option("--override_file", help="File to override input options", default=None)
@click.option("--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url")
@click.option("--app", help="App name, appid field on Cavaita app page")
def create_task(
	input_bam_list,
	input_pe_reads_list,
	input_pe_mates_list,
	input_pe_rgs_list,
	input_se_reads_list,
	input_se_rgs_list,
	reference_tar,
	cram_reference,
	biospecimen_name,
	output_basename,
	dbsnp_vcf,
	dbsnp_idx,
	knownsites,
	knownsites_indexes,
	contamination_sites_bed,
	contamination_sites_mu,
	contamination_sites_ud,
	wgs_calling_interval_list,
	wgs_coverage_interval_list,
	wgs_evaluation_interval_list,
	wxs_bait_interval_list,
	wxs_target_interval_list,
	run_bam_processing,
	run_pe_reads_processing,
	run_se_reads_processing,
	run_hs_metrics,
	run_wgs_metrics,
	run_agg_metrics,
	run_sex_metrics,
	run_gvcf_processing,
	cutadapt_r1_adapter,
	cutadapt_r2_adapter,
	cutadapt_min_len,
	cutadapt_quality_base,
	cutadapt_quality_cutoff,
	min_alignment_score,
	bamtofastq_cpu,
	run_t1k,
	hla_dna_ref_seqs,
	hla_dna_gene_coords,
	t1k_abnormal_unmap_flag,
	t1k_ram,
	profile,
	task_file,
	override_file,
	project,
	app,
):
	api = hf.parse_config(profile)
	task_ids = []
	today = datetime.datetime.now().strftime("%Y%m%d")

	if override_file:
		with open(override_file, "r") as f:
			line_num = 0
			overrides = []
			for line in f:
				if line_num == 0:
					overrides = line.strip().split("\t")
				else:
					line_vals = line.strip().split("\t")
					app_inputs = {}
					if "input_bam_list" in overrides:
						input_bam_list = line_vals[overrides.index("input_bam_list")]
					if input_bam_list is not None:
						input_bam_list = input_bam_list.split(",")
						for i in range(len(input_bam_list)):
							input_bam_list[i] = hf.get_file_obj(api, project, input_bam_list[i])
						app_inputs["input_bam_list"] = input_bam_list
					if "input_pe_reads_list" in overrides:
						input_pe_reads_list = line_vals[overrides.index("input_pe_reads_list")]
					if input_pe_reads_list is not None:
						input_pe_reads_list = input_pe_reads_list.split(",")
						for i in range(len(input_pe_reads_list)):
							input_pe_reads_list[i] = hf.get_file_obj(api, project, input_pe_reads_list[i])
						app_inputs["input_pe_reads_list"] = input_pe_reads_list
					if "input_pe_mates_list" in overrides:
						input_pe_mates_list = line_vals[overrides.index("input_pe_mates_list")]
					if input_pe_mates_list is not None:
						input_pe_mates_list = input_pe_mates_list.split(",")
						for i in range(len(input_pe_mates_list)):
							input_pe_mates_list[i] = hf.get_file_obj(api, project, input_pe_mates_list[i])
						app_inputs["input_pe_mates_list"] = input_pe_mates_list
					if "input_pe_rgs_list" in overrides:
						input_pe_rgs_list = line_vals[overrides.index("input_pe_rgs_list")]
					if input_pe_rgs_list is not None:
						input_pe_rgs_list = input_pe_rgs_list.split(",")
						for i in range(len(input_pe_rgs_list)):
							input_pe_rgs_list[i] = input_pe_rgs_list[i]
						app_inputs["input_pe_rgs_list"] = input_pe_rgs_list
					if "input_se_reads_list" in overrides:
						input_se_reads_list = line_vals[overrides.index("input_se_reads_list")]
					if input_se_reads_list is not None:
						input_se_reads_list = input_se_reads_list.split(",")
						for i in range(len(input_se_reads_list)):
							input_se_reads_list[i] = hf.get_file_obj(api, project, input_se_reads_list[i])
						app_inputs["input_se_reads_list"] = input_se_reads_list
					if "input_se_rgs_list" in overrides:
						input_se_rgs_list = line_vals[overrides.index("input_se_rgs_list")]
					if input_se_rgs_list is not None:
						input_se_rgs_list = input_se_rgs_list.split(",")
						for i in range(len(input_se_rgs_list)):
							input_se_rgs_list[i] = input_se_rgs_list[i]
						app_inputs["input_se_rgs_list"] = input_se_rgs_list
					if "reference_tar" in overrides:
						reference_tar = line_vals[overrides.index("reference_tar")]
					if reference_tar is not None:
						app_inputs["reference_tar"] = hf.get_file_obj(api, project, reference_tar)
					if "cram_reference" in overrides:
						cram_reference = line_vals[overrides.index("cram_reference")]
					if cram_reference is not None:
						app_inputs["cram_reference"] = hf.get_file_obj(api, project, cram_reference)
					if "biospecimen_name" in overrides:
						biospecimen_name = line_vals[overrides.index("biospecimen_name")]
					if biospecimen_name is not None:
						app_inputs["biospecimen_name"] = biospecimen_name
					if "output_basename" in overrides:
						output_basename = f"{line_vals[overrides.index("output_basename")]}_{today}"
					if output_basename is not None:
						app_inputs["output_basename"] = output_basename
					if "dbsnp_vcf" in overrides:
						dbsnp_vcf = line_vals[overrides.index("dbsnp_vcf")]
					if dbsnp_vcf is not None:
						app_inputs["dbsnp_vcf"] = hf.get_file_obj(api, project, dbsnp_vcf)
					if "dbsnp_idx" in overrides:
						dbsnp_idx = line_vals[overrides.index("dbsnp_idx")]
					if dbsnp_idx is not None:
						app_inputs["dbsnp_idx"] = hf.get_file_obj(api, project, dbsnp_idx)
					if "knownsites" in overrides:
						knownsites = line_vals[overrides.index("knownsites")]
					if knownsites is not None:
						knownsites = knownsites.split(",")
						for i in range(len(knownsites)):
							knownsites[i] = hf.get_file_obj(api, project, knownsites[i])
						app_inputs["knownsites"] = knownsites
					if "knownsites_indexes" in overrides:
						knownsites_indexes = line_vals[overrides.index("knownsites_indexes")]
					if knownsites_indexes is not None:
						knownsites_indexes = knownsites_indexes.split(",")
						for i in range(len(knownsites_indexes)):
							knownsites_indexes[i] = hf.get_file_obj(api, project, knownsites_indexes[i])
						app_inputs["knownsites_indexes"] = knownsites_indexes
					if "contamination_sites_bed" in overrides:
						contamination_sites_bed = line_vals[overrides.index("contamination_sites_bed")]
					if contamination_sites_bed is not None:
						app_inputs["contamination_sites_bed"] = hf.get_file_obj(api, project, contamination_sites_bed)
					if "contamination_sites_mu" in overrides:
						contamination_sites_mu = line_vals[overrides.index("contamination_sites_mu")]
					if contamination_sites_mu is not None:
						app_inputs["contamination_sites_mu"] = hf.get_file_obj(api, project, contamination_sites_mu)
					if "contamination_sites_ud" in overrides:
						contamination_sites_ud = line_vals[overrides.index("contamination_sites_ud")]
					if contamination_sites_ud is not None:
						app_inputs["contamination_sites_ud"] = hf.get_file_obj(api, project, contamination_sites_ud)
					if "wgs_calling_interval_list" in overrides:
						wgs_calling_interval_list = line_vals[overrides.index("wgs_calling_interval_list")]
					if wgs_calling_interval_list is not None:
						app_inputs["wgs_calling_interval_list"] = hf.get_file_obj(api, project, wgs_calling_interval_list)
					if "wgs_coverage_interval_list" in overrides:
						wgs_coverage_interval_list = line_vals[overrides.index("wgs_coverage_interval_list")]
					if wgs_coverage_interval_list is not None:
						app_inputs["wgs_coverage_interval_list"] = hf.get_file_obj(api, project, wgs_coverage_interval_list)
					if "wgs_evaluation_interval_list" in overrides:
						wgs_evaluation_interval_list = line_vals[overrides.index("wgs_evaluation_interval_list")]
					if wgs_evaluation_interval_list is not None:
						app_inputs["wgs_evaluation_interval_list"] = hf.get_file_obj(api, project, wgs_evaluation_interval_list)
					if "wxs_bait_interval_list" in overrides:
						wxs_bait_interval_list = line_vals[overrides.index("wxs_bait_interval_list")]
					if wxs_bait_interval_list is not None:
						app_inputs["wxs_bait_interval_list"] = hf.get_file_obj(api, project, wxs_bait_interval_list)
					if "wxs_target_interval_list" in overrides:
						wxs_target_interval_list = line_vals[overrides.index("wxs_target_interval_list")]
					if wxs_target_interval_list is not None:
						app_inputs["wxs_target_interval_list"] = hf.get_file_obj(api, project, wxs_target_interval_list)
					if "run_bam_processing" in overrides:
						run_bam_processing = line_vals[overrides.index("run_bam_processing")]
					if run_bam_processing is not None:
						app_inputs["run_bam_processing"] = run_bam_processing.lower() == "true"
					if "run_pe_reads_processing" in overrides:
						run_pe_reads_processing = line_vals[overrides.index("run_pe_reads_processing")]
					if run_pe_reads_processing is not None:
						app_inputs["run_pe_reads_processing"] = run_pe_reads_processing.lower() == "true"
					if "run_se_reads_processing" in overrides:
						run_se_reads_processing = line_vals[overrides.index("run_se_reads_processing")]
					if run_se_reads_processing is not None:
						app_inputs["run_se_reads_processing"] = run_se_reads_processing.lower() == "true"
					if "run_hs_metrics" in overrides:
						run_hs_metrics = line_vals[overrides.index("run_hs_metrics")]
					if run_hs_metrics is not None:
						app_inputs["run_hs_metrics"] = run_hs_metrics.lower() == "true"
					if "run_wgs_metrics" in overrides:
						run_wgs_metrics = line_vals[overrides.index("run_wgs_metrics")]
					if run_wgs_metrics is not None:
						app_inputs["run_wgs_metrics"] = run_wgs_metrics.lower() == "true"
					if "run_agg_metrics" in overrides:
						run_agg_metrics = line_vals[overrides.index("run_agg_metrics")]
					if run_agg_metrics is not None:
						app_inputs["run_agg_metrics"] = run_agg_metrics.lower() == "true"
					if "run_sex_metrics" in overrides:
						run_sex_metrics = line_vals[overrides.index("run_sex_metrics")]
					if run_sex_metrics is not None:
						app_inputs["run_sex_metrics"] = run_sex_metrics.lower() == "true"
					if "run_gvcf_processing" in overrides:
						run_gvcf_processing = line_vals[overrides.index("run_gvcf_processing")]
					if run_gvcf_processing is not None:
						app_inputs["run_gvcf_processing"] = run_gvcf_processing.lower() == "true"
					if "cutadapt_r1_adapter" in overrides:
						cutadapt_r1_adapter = line_vals[overrides.index("cutadapt_r1_adapter")]
					if cutadapt_r1_adapter is not None:
						app_inputs["cutadapt_r1_adapter"] = cutadapt_r1_adapter
					if "cutadapt_r2_adapter" in overrides:
						cutadapt_r2_adapter = line_vals[overrides.index("cutadapt_r2_adapter")]
					if cutadapt_r2_adapter is not None:
						app_inputs["cutadapt_r2_adapter"] = cutadapt_r2_adapter
					if "cutadapt_min_len" in overrides:
						cutadapt_min_len = line_vals[overrides.index("cutadapt_min_len")]
					if cutadapt_min_len is not None:
						app_inputs["cutadapt_min_len"] = int(cutadapt_min_len)
					if "cutadapt_quality_base" in overrides:
						cutadapt_quality_base = line_vals[overrides.index("cutadapt_quality_base")]
					if cutadapt_quality_base is not None:
						app_inputs["cutadapt_quality_base"] = int(cutadapt_quality_base)
					if "cutadapt_quality_cutoff" in overrides:
						cutadapt_quality_cutoff = line_vals[overrides.index("cutadapt_quality_cutoff")]
					if cutadapt_quality_cutoff is not None:
						app_inputs["cutadapt_quality_cutoff"] = cutadapt_quality_cutoff
					if "min_alignment_score" in overrides:
						min_alignment_score = line_vals[overrides.index("min_alignment_score")]
					if min_alignment_score is not None:
						app_inputs["min_alignment_score"] = int(min_alignment_score)
					if "bamtofastq_cpu" in overrides:
						bamtofastq_cpu = line_vals[overrides.index("bamtofastq_cpu")]
					if bamtofastq_cpu is not None:
						app_inputs["bamtofastq_cpu"] = int(bamtofastq_cpu)
					if "run_t1k" in overrides:
						run_t1k = line_vals[overrides.index("run_t1k")]
					if run_t1k is not None:
						app_inputs["run_t1k"] = run_t1k.lower() == "true"
					if "hla_dna_ref_seqs" in overrides:
						hla_dna_ref_seqs = line_vals[overrides.index("hla_dna_ref_seqs")]
					if hla_dna_ref_seqs is not None:
						app_inputs["hla_dna_ref_seqs"] = hf.get_file_obj(api, project, hla_dna_ref_seqs)
					if "hla_dna_gene_coords" in overrides:
						hla_dna_gene_coords = line_vals[overrides.index("hla_dna_gene_coords")]
					if hla_dna_gene_coords is not None:
						app_inputs["hla_dna_gene_coords"] = hf.get_file_obj(api, project, hla_dna_gene_coords)
					if "t1k_abnormal_unmap_flag" in overrides:
						t1k_abnormal_unmap_flag = line_vals[overrides.index("t1k_abnormal_unmap_flag")]
					if t1k_abnormal_unmap_flag is not None:
						app_inputs["t1k_abnormal_unmap_flag"] = t1k_abnormal_unmap_flag.lower() == "true"
					if "t1k_ram" in overrides:
						t1k_ram = line_vals[overrides.index("t1k_ram")]
					if t1k_ram is not None:
						app_inputs["t1k_ram"] = int(t1k_ram)
					new_task = api.tasks.create(
						name=f"kfdrc_alignment_wf_{output_basename}",
						project=project,
						app=app,
						inputs = app_inputs
					)
					print(new_task.name, new_task.status, new_task.id)
					task_ids.append(new_task.id)
					time.sleep(20)
				line_num += 1
	else:
		app_inputs = {}
		if "input_bam_list" in overrides:
			input_bam_list = line_vals[overrides.index("input_bam_list")]
		if input_bam_list is not None:
			input_bam_list = input_bam_list.split(",")
			for i in range(len(input_bam_list)):
				input_bam_list[i] = hf.get_file_obj(api, project, input_bam_list[i])
			app_inputs["input_bam_list"] = input_bam_list
		if "input_pe_reads_list" in overrides:
			input_pe_reads_list = line_vals[overrides.index("input_pe_reads_list")]
		if input_pe_reads_list is not None:
			input_pe_reads_list = input_pe_reads_list.split(",")
			for i in range(len(input_pe_reads_list)):
				input_pe_reads_list[i] = hf.get_file_obj(api, project, input_pe_reads_list[i])
			app_inputs["input_pe_reads_list"] = input_pe_reads_list
		if "input_pe_mates_list" in overrides:
			input_pe_mates_list = line_vals[overrides.index("input_pe_mates_list")]
		if input_pe_mates_list is not None:
			input_pe_mates_list = input_pe_mates_list.split(",")
			for i in range(len(input_pe_mates_list)):
				input_pe_mates_list[i] = hf.get_file_obj(api, project, input_pe_mates_list[i])
			app_inputs["input_pe_mates_list"] = input_pe_mates_list
		if "input_pe_rgs_list" in overrides:
			input_pe_rgs_list = line_vals[overrides.index("input_pe_rgs_list")]
		if input_pe_rgs_list is not None:
			input_pe_rgs_list = input_pe_rgs_list.split(",")
			for i in range(len(input_pe_rgs_list)):
				input_pe_rgs_list[i] = input_pe_rgs_list[i]
			app_inputs["input_pe_rgs_list"] = input_pe_rgs_list
		if "input_se_reads_list" in overrides:
			input_se_reads_list = line_vals[overrides.index("input_se_reads_list")]
		if input_se_reads_list is not None:
			input_se_reads_list = input_se_reads_list.split(",")
			for i in range(len(input_se_reads_list)):
				input_se_reads_list[i] = hf.get_file_obj(api, project, input_se_reads_list[i])
			app_inputs["input_se_reads_list"] = input_se_reads_list
		if "input_se_rgs_list" in overrides:
			input_se_rgs_list = line_vals[overrides.index("input_se_rgs_list")]
		if input_se_rgs_list is not None:
			input_se_rgs_list = input_se_rgs_list.split(",")
			for i in range(len(input_se_rgs_list)):
				input_se_rgs_list[i] = input_se_rgs_list[i]
			app_inputs["input_se_rgs_list"] = input_se_rgs_list
		if "reference_tar" in overrides:
			reference_tar = line_vals[overrides.index("reference_tar")]
		if reference_tar is not None:
			app_inputs["reference_tar"] = hf.get_file_obj(api, project, reference_tar)
		if "cram_reference" in overrides:
			cram_reference = line_vals[overrides.index("cram_reference")]
		if cram_reference is not None:
			app_inputs["cram_reference"] = hf.get_file_obj(api, project, cram_reference)
		if "biospecimen_name" in overrides:
			biospecimen_name = line_vals[overrides.index("biospecimen_name")]
		if biospecimen_name is not None:
			app_inputs["biospecimen_name"] = biospecimen_name
		if "output_basename" in overrides:
			output_basename = f"{line_vals[overrides.index("output_basename")]}_{today}"
		if output_basename is not None:
			app_inputs["output_basename"] = output_basename
		if "dbsnp_vcf" in overrides:
			dbsnp_vcf = line_vals[overrides.index("dbsnp_vcf")]
		if dbsnp_vcf is not None:
			app_inputs["dbsnp_vcf"] = hf.get_file_obj(api, project, dbsnp_vcf)
		if "dbsnp_idx" in overrides:
			dbsnp_idx = line_vals[overrides.index("dbsnp_idx")]
		if dbsnp_idx is not None:
			app_inputs["dbsnp_idx"] = hf.get_file_obj(api, project, dbsnp_idx)
		if "knownsites" in overrides:
			knownsites = line_vals[overrides.index("knownsites")]
		if knownsites is not None:
			knownsites = knownsites.split(",")
			for i in range(len(knownsites)):
				knownsites[i] = hf.get_file_obj(api, project, knownsites[i])
			app_inputs["knownsites"] = knownsites
		if "knownsites_indexes" in overrides:
			knownsites_indexes = line_vals[overrides.index("knownsites_indexes")]
		if knownsites_indexes is not None:
			knownsites_indexes = knownsites_indexes.split(",")
			for i in range(len(knownsites_indexes)):
				knownsites_indexes[i] = hf.get_file_obj(api, project, knownsites_indexes[i])
			app_inputs["knownsites_indexes"] = knownsites_indexes
		if "contamination_sites_bed" in overrides:
			contamination_sites_bed = line_vals[overrides.index("contamination_sites_bed")]
		if contamination_sites_bed is not None:
			app_inputs["contamination_sites_bed"] = hf.get_file_obj(api, project, contamination_sites_bed)
		if "contamination_sites_mu" in overrides:
			contamination_sites_mu = line_vals[overrides.index("contamination_sites_mu")]
		if contamination_sites_mu is not None:
			app_inputs["contamination_sites_mu"] = hf.get_file_obj(api, project, contamination_sites_mu)
		if "contamination_sites_ud" in overrides:
			contamination_sites_ud = line_vals[overrides.index("contamination_sites_ud")]
		if contamination_sites_ud is not None:
			app_inputs["contamination_sites_ud"] = hf.get_file_obj(api, project, contamination_sites_ud)
		if "wgs_calling_interval_list" in overrides:
			wgs_calling_interval_list = line_vals[overrides.index("wgs_calling_interval_list")]
		if wgs_calling_interval_list is not None:
			app_inputs["wgs_calling_interval_list"] = hf.get_file_obj(api, project, wgs_calling_interval_list)
		if "wgs_coverage_interval_list" in overrides:
			wgs_coverage_interval_list = line_vals[overrides.index("wgs_coverage_interval_list")]
		if wgs_coverage_interval_list is not None:
			app_inputs["wgs_coverage_interval_list"] = hf.get_file_obj(api, project, wgs_coverage_interval_list)
		if "wgs_evaluation_interval_list" in overrides:
			wgs_evaluation_interval_list = line_vals[overrides.index("wgs_evaluation_interval_list")]
		if wgs_evaluation_interval_list is not None:
			app_inputs["wgs_evaluation_interval_list"] = hf.get_file_obj(api, project, wgs_evaluation_interval_list)
		if "wxs_bait_interval_list" in overrides:
			wxs_bait_interval_list = line_vals[overrides.index("wxs_bait_interval_list")]
		if wxs_bait_interval_list is not None:
			app_inputs["wxs_bait_interval_list"] = hf.get_file_obj(api, project, wxs_bait_interval_list)
		if "wxs_target_interval_list" in overrides:
			wxs_target_interval_list = line_vals[overrides.index("wxs_target_interval_list")]
		if wxs_target_interval_list is not None:
			app_inputs["wxs_target_interval_list"] = hf.get_file_obj(api, project, wxs_target_interval_list)
		if "run_bam_processing" in overrides:
			run_bam_processing = line_vals[overrides.index("run_bam_processing")]
		if run_bam_processing is not None:
			app_inputs["run_bam_processing"] = run_bam_processing.lower() == "true"
		if "run_pe_reads_processing" in overrides:
			run_pe_reads_processing = line_vals[overrides.index("run_pe_reads_processing")]
		if run_pe_reads_processing is not None:
			app_inputs["run_pe_reads_processing"] = run_pe_reads_processing.lower() == "true"
		if "run_se_reads_processing" in overrides:
			run_se_reads_processing = line_vals[overrides.index("run_se_reads_processing")]
		if run_se_reads_processing is not None:
			app_inputs["run_se_reads_processing"] = run_se_reads_processing.lower() == "true"
		if "run_hs_metrics" in overrides:
			run_hs_metrics = line_vals[overrides.index("run_hs_metrics")]
		if run_hs_metrics is not None:
			app_inputs["run_hs_metrics"] = run_hs_metrics.lower() == "true"
		if "run_wgs_metrics" in overrides:
			run_wgs_metrics = line_vals[overrides.index("run_wgs_metrics")]
		if run_wgs_metrics is not None:
			app_inputs["run_wgs_metrics"] = run_wgs_metrics.lower() == "true"
		if "run_agg_metrics" in overrides:
			run_agg_metrics = line_vals[overrides.index("run_agg_metrics")]
		if run_agg_metrics is not None:
			app_inputs["run_agg_metrics"] = run_agg_metrics.lower() == "true"
		if "run_sex_metrics" in overrides:
			run_sex_metrics = line_vals[overrides.index("run_sex_metrics")]
		if run_sex_metrics is not None:
			app_inputs["run_sex_metrics"] = run_sex_metrics.lower() == "true"
		if "run_gvcf_processing" in overrides:
			run_gvcf_processing = line_vals[overrides.index("run_gvcf_processing")]
		if run_gvcf_processing is not None:
			app_inputs["run_gvcf_processing"] = run_gvcf_processing.lower() == "true"
		if "cutadapt_r1_adapter" in overrides:
			cutadapt_r1_adapter = line_vals[overrides.index("cutadapt_r1_adapter")]
		if cutadapt_r1_adapter is not None:
			app_inputs["cutadapt_r1_adapter"] = cutadapt_r1_adapter
		if "cutadapt_r2_adapter" in overrides:
			cutadapt_r2_adapter = line_vals[overrides.index("cutadapt_r2_adapter")]
		if cutadapt_r2_adapter is not None:
			app_inputs["cutadapt_r2_adapter"] = cutadapt_r2_adapter
		if "cutadapt_min_len" in overrides:
			cutadapt_min_len = line_vals[overrides.index("cutadapt_min_len")]
		if cutadapt_min_len is not None:
			app_inputs["cutadapt_min_len"] = int(cutadapt_min_len)
		if "cutadapt_quality_base" in overrides:
			cutadapt_quality_base = line_vals[overrides.index("cutadapt_quality_base")]
		if cutadapt_quality_base is not None:
			app_inputs["cutadapt_quality_base"] = int(cutadapt_quality_base)
		if "cutadapt_quality_cutoff" in overrides:
			cutadapt_quality_cutoff = line_vals[overrides.index("cutadapt_quality_cutoff")]
		if cutadapt_quality_cutoff is not None:
			app_inputs["cutadapt_quality_cutoff"] = cutadapt_quality_cutoff
		if "min_alignment_score" in overrides:
			min_alignment_score = line_vals[overrides.index("min_alignment_score")]
		if min_alignment_score is not None:
			app_inputs["min_alignment_score"] = int(min_alignment_score)
		if "bamtofastq_cpu" in overrides:
			bamtofastq_cpu = line_vals[overrides.index("bamtofastq_cpu")]
		if bamtofastq_cpu is not None:
			app_inputs["bamtofastq_cpu"] = int(bamtofastq_cpu)
		if "run_t1k" in overrides:
			run_t1k = line_vals[overrides.index("run_t1k")]
		if run_t1k is not None:
			app_inputs["run_t1k"] = run_t1k.lower() == "true"
		if "hla_dna_ref_seqs" in overrides:
			hla_dna_ref_seqs = line_vals[overrides.index("hla_dna_ref_seqs")]
		if hla_dna_ref_seqs is not None:
			app_inputs["hla_dna_ref_seqs"] = hf.get_file_obj(api, project, hla_dna_ref_seqs)
		if "hla_dna_gene_coords" in overrides:
			hla_dna_gene_coords = line_vals[overrides.index("hla_dna_gene_coords")]
		if hla_dna_gene_coords is not None:
			app_inputs["hla_dna_gene_coords"] = hf.get_file_obj(api, project, hla_dna_gene_coords)
		if "t1k_abnormal_unmap_flag" in overrides:
			t1k_abnormal_unmap_flag = line_vals[overrides.index("t1k_abnormal_unmap_flag")]
		if t1k_abnormal_unmap_flag is not None:
			app_inputs["t1k_abnormal_unmap_flag"] = t1k_abnormal_unmap_flag.lower() == "true"
		if "t1k_ram" in overrides:
			t1k_ram = line_vals[overrides.index("t1k_ram")]
		if t1k_ram is not None:
			app_inputs["t1k_ram"] = int(t1k_ram)
		new_task = api.tasks.create(
			name=f"kfdrc_alignment_wf_{output_basename}",
			project=project,
			app=app,
			inputs = app_inputs
		)
		print(new_task.name, new_task.status, new_task.id)
		task_ids.append(new_task.id)

	with open(task_file, "w") as f:
		for task_id in task_ids:
			f.write(f"{task_id}\n")

if __name__ == "__main__":
	create_task()
