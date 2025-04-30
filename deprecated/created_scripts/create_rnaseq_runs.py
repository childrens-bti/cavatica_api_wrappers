import click
import time
from pathlib import Path
from helper_functions import helper_functions as hf

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
@click.command(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option("--reference_fasta", help="GRCh38.primary_assembly.genome.fa", default="GRCh38.primary_assembly.genome.fa")
@click.option("--output_basename", help="String to use as basename for outputs. Will use read1 file basename if null")
@click.option("--input_alignment_files", help="List of input SAM/BAM/CRAM files to process")
@click.option("--input_pe_reads", help="List of R1 paired end FASTQ files to process")
@click.option("--input_pe_mates", help="List of R2 paired end FASTQ files to process")
@click.option("--input_se_reads", help="List of single end FASTQ files to process")
@click.option("--input_pe_rg_strs", help="List of RG strings to use in PE processing")
@click.option("--input_se_rg_strs", help="List of RG strings to use in SE processing")
@click.option("--cram_reference", help="If any input alignment files are CRAM, provide the reference used to create them")
@click.option("--is_paired_end", help="For alignment files inputs, are the reads paired end?")
@click.option("--r1_adapter", help="!Warning this will be applied to all R1 reads (PE, SE, and reads from alignment files)! If you have multiple adapters, manually trim your reads before input. If they share the same adapter, supply adapter here")
@click.option("--r2_adapter", help="!Warning this will be applied to all R2 reads (PE and reads from alignment files)! If you have multiple adapters, manually trim your reads before input. If they share the same adapter, supply adapter here")
@click.option("--min_len", help="If trimming adapters, what is the minimum length reads should have post trimming")
@click.option("--quality_base", help="Phred scale used for quality scores of the reads")
@click.option("--quality_cutoff", help="Quality trim cutoff, see https://cutadapt.readthedocs.io/en/v3.4/guide.html#quality-trimming for how 5' 3' is handled")
@click.option("--wf_strand_param", help="use 'default' for unstranded/auto, 'rf-stranded' if read1 in the fastq read pairs is reverse complement to the transcript, 'fr-stranded' if read1 same sense as transcript")
@click.option("--gtf_anno", help="General transfer format (gtf) file with gene models corresponding to fasta reference", default="gencode.v39.primary_assembly.annotation.gtf")
@click.option("--star_fusion_genome_untar_path", help="This is what the path will be when genome_tar is unpackaged", default="GRCh38_v39_CTAT_lib_Mar242022.CUSTOM")
@click.option("--read_length_median", help="The median read length for the reads provided.")
@click.option("--read_length_stddev", help="Standard Deviation of the median read length.")
@click.option("--samtools_fastq_cores", help="Num cores for align2fastq conversion, if input is an alignment file", default="16")
@click.option("--stargenome", help="Tar gzipped reference that will be unzipped at run time", default="STAR_2.7.10a_GENCODE39.tar.gz")
@click.option("--runthreadn", default="36", help="Adjust this value to change number of cores used by STAR.")
@click.option("--twopassmode", default="Basic", help="Enable two pass mode to detect novel splice events. Default is basic (on).")
@click.option("--alignsjoverhangmin", default="8", help="minimum overhang for unannotated junctions. ENCODE default used.")
@click.option("--outfiltermismatchnoverlmax", default="0.1", help="alignment will be output only if its ratio of mismatches to *mapped* length is less than or equal to this value")
@click.option("--outfiltertype", default="BySJout", help="type of filtering. Normal: standard filtering using only current alignment. BySJout (default): keep only those reads that contain junctions that passed filtering into SJ.out.tab.")
@click.option("--outfilterscoreminoverlread", default="0.33", help="alignment will be output only if its score is higher than or equal to this value, normalized to read length (sum of mate's lengths for paired-end reads)")
@click.option("--outfiltermatchnminoverlread", default="0.33", help="alignment will be output only if the number of matched bases is higher than or equal to this value., normalized to the read length (sum of mates' lengths for paired-end reads)")
@click.option("--outreadsunmapped", default="None", help="output of unmapped and partially mapped (i.e. mapped only one mate of a paired end read) reads in separate file(s). none (default): no output. Fastx: output in separate fasta/fastq files, Unmapped.out.mate1/2.")
@click.option("--limitsjdbinsertnsj", default="1200000", help="maximum number of junction to be inserted to the genome on the fly at the mapping stage, including those from annotations and those detected in the 1st step of the 2-pass run")
@click.option("--outsamstrandfield", default="intronMotif", help="Cufflinks-like strand field flag. None: not used. intronMotif (default): strand derived from the intron motif. This option changes the output alignments: reads with inconsistent and/or non-canonical introns are filtered out.")
@click.option("--outfilterintronmotifs", default="None", help="filter alignment using their motifs. None (default): no filtering. RemoveNoncanonical: filter out alignments that contain non-canonical junctions RemoveNoncanonicalUnannotated: filter out alignments that contain non-canonical unannotated junctions when using annotated splice junctions database. The annotated non-canonical junctions will be kept.")
@click.option("--alignsoftclipatreferenceends", default="Yes", help="allow the soft-clipping of the alignments past the end of the chromosomes. Yes (default): allow. No: prohibit, useful for compatibility with Cufflinks")
@click.option("--quantmode", default="TranscriptomeSAM GeneCounts", help="types of quantification requested. -: none. TranscriptomeSAM: output SAM/BAM alignments to transcriptome into a separate file GeneCounts: count reads per gene. Choices are additive, so default is 'TranscriptomeSAM GeneCounts'")
@click.option("--outsamtype", default="BAM Unsorted", help="type of SAM/BAM output. None: no SAM/BAM output. Otherwise, first word is output type (BAM or SAM), second is sort type (Unsorted or SortedByCoordinate)")
@click.option("--outsamunmapped", default="Within", help="output of unmapped reads in the SAM format. None: no output. Within (default): output unmapped reads within the main SAM file (i.e. Aligned.out.sam) Within KeepPairs: record unmapped mate for each alignment, and, in case of unsorted output, keep it adjacent to its mapped mate. Only affects multi-mapping reads")
@click.option("--genomeload", default="NoSharedMemory", help="mode of shared memory usage for the genome file. In this context, the default value makes the most sense, the others are their as a courtesy.")
@click.option("--chimmainsegmentmultnmax", default="1", help="maximum number of multi-alignments for the main chimeric segment. =1 will prohibit multimapping main segments")
@click.option("--outsamattributes", default="NH HI AS nM NM ch RG", help="a string of desired SAM attributes, in the order desired for the output SAM. Tags can be listed in any combination/order. Please refer to the STAR manual, as there are numerous combinations: https://raw.githubusercontent.com/alexdobin/star_2.7.10a/master/doc/STARmanual.pdf")
@click.option("--aligninsertionflush", default="None", help="how to flush ambiguous insertion positions. None (default): insertions not flushed. Right: insertions flushed to the right. STAR Fusion recommended (SF)")
@click.option("--alignintronmax", default="1000000", help="maximum intron size. SF recommends 100000")
@click.option("--alignmatesgapmax", default="1000000", help="maximum genomic distance between mates, SF recommends 100000 to avoid readthru fusions within 100k")
@click.option("--alignsjdboverhangmin", default="1", help="minimum overhang for annotated junctions. SF recommends 10")
@click.option("--outfiltermismatchnmax", default="999", help="maximum number of mismatches per pair, large number switches off this filter")
@click.option("--alignsjstitchmismatchnmax", default="5 -1 5 5", help="maximum number of mismatches for stitching of the splice junctions. Value '5 -1 5 5' improves SF chimeric junctions, also recommended by arriba (AR)")
@click.option("--alignsplicedmatemaplmin", default="0", help="minimum mapped length for a read mate that is spliced. SF recommends 30")
@click.option("--alignsplicedmatemaplminoverlmate", default="0.5", help="alignSplicedMateMapLmin normalized to mate length. SF recommends 0, AR 0.5")
@click.option("--chimjunctionoverhangmin", default="10", help="minimum overhang for a chimeric junction. SF recommends 8, AR 10")
@click.option("--chimmultimapnmax", default="50", help="maximum number of chimeric multi-alignments. SF recommends 20, AR 50.")
@click.option("--chimmultimapscorerange", default="1", help="the score range for multi-mapping chimeras below the best chimeric score. Only works with chimMultimapNmax > 1. SF recommends 3")
@click.option("--chimnonchimscoredropmin", default="20", help="int>=0: to trigger chimeric detection, the drop in the best non-chimeric alignment score with respect to the read length has to be greater than this value. SF recommends 10")
@click.option("--chimoutjunctionformat", default="1", help="formatting type for the Chimeric.out.junction file, value 1 REQUIRED for SF")
@click.option("--chimouttype", default="Junctions WithinBAM SoftClip", help="type of chimeric output. Args are additive, and defined as such - Junctions: Chimeric.out.junction. SeparateSAMold: output old SAM into separate Chimeric.out.sam file WithinBAM: output into main aligned BAM files (Aligned.*.bam). WithinBAM HardClip: hard-clipping in the CIGAR for supplemental chimeric alignments WithinBAM SoftClip:soft-clipping in the CIGAR for supplemental chimeric alignments")
@click.option("--chimscoredropmax", default="30", help="max drop (difference) of chimeric score (the sum of scores of all chimeric segments) from the read length. AR recommends 30")
@click.option("--chimscorejunctionnongtag", default="-1", help="penalty for a non-GT/AG chimeric junction. default -1, SF recommends -4, AR -1")
@click.option("--chimscoreseparation", default="1", help="int>=0: minimum difference (separation) between the best chimeric score and the next one. AR recommends 1")
@click.option("--chimsegmentmin", default="10", help="minimum length of chimeric segment length, if ==0, no chimeric output. REQUIRED for SF, 12 is their default, AR recommends 10")
@click.option("--chimsegmentreadgapmax", default="3", help="maximum gap in the read sequence between chimeric segments. AR recommends 3")
@click.option("--outfiltermultimapnmax", default="50", help="max number of multiple alignments allowed for a read: if exceeded, the read is considered unmapped. ENCODE value is default. AR recommends 50")
@click.option("--peoverlapmmp", default="0.01", help="maximum proportion of mismatched bases in the overlap area. SF recommends 0.1")
@click.option("--peoverlapnbasesmin", default="10", help="minimum number of overlap bases to trigger mates merging and realignment. Specify >0 value to switch on the 'merging of overlapping mates'algorithm. SF recommends 12,  AR recommends 10")
@click.option("--arriba_memory", help="Mem intensive tool. Set in GB", default="64")
@click.option("--fusiongenome", help="STAR-Fusion CTAT Genome lib", default="GRCh38_v39_CTAT_lib_Mar242022.CUSTOM.tar.gz")
@click.option("--compress_chimeric_junction", default="True", help="If part of a workflow, recommend compressing this file as final output")
@click.option("--rnaseqc_gtf", help="gtf file from `gtf_anno` that has been collapsed GTEx-style", default="gencode.v39.primary_assembly.rnaseqc.stranded.gtf")
@click.option("--kallisto_idx", help="Specialized index of a **transcriptome** fasta file for kallisto", default="RSEM_GENCODE39.transcripts.kallisto.idx")
@click.option("--rsemgenome", help="RSEM reference tar ball", default="RSEM_GENCODE39.tar.gz")
@click.option("--estimate_rspd", help="Set this option if you want to estimate the read start position distribution (RSPD) from data", default="True")
@click.option("--sample_name", help="Sample ID of the input reads. If not provided, will use reads1 file basename.")
@click.option("--annofuse_col_num", help="0-based column number in file of fusion name.", default="30")
@click.option("--fusion_annotator_ref", help="Tar ball with fusion_annot_lib.idx and blast_pairs.idx from STAR-Fusion CTAT Genome lib. Can be same as FusionGenome, but only two files needed from that package", default="GRCh38_v39_fusion_annot_custom.tar.gz")
@click.option("--rmats_variable_read_length", default="True", help="Allow reads with lengths that differ from --readLength to be processed. --readLength will still be used to determine IncFormLen and SkipFormLen.")
@click.option("--rmats_novel_splice_sites", help="Select for novel splice site detection or unannotated splice sites. 'true' to detect or add this parameter, 'false' to disable denovo detection. Tool Default: false")
@click.option("--rmats_stat_off", help="Select to skip statistical analysis, either between two groups or on single sample group. 'true' to add this parameter. Tool default: false")
@click.option("--rmats_allow_clipping", help="Allow alignments with soft or hard clipping to be used.")
@click.option("--rmats_threads", help="Threads to allocate to RMATs.")
@click.option("--rmats_ram", help="GB of RAM to allocate to RMATs.")
@click.option("--run_t1k", default="True", help="Set to false to disable T1k HLA typing")
@click.option("--hla_rna_ref_seqs", help="FASTA file containing the HLA allele reference sequences for RNA.", default="hla_v3.43.0_gencode_v39_rna_seq.fa")
@click.option("--hla_rna_gene_coords", help="FASTA file containing the coordinates of the HLA genes for RNA.", default="hla_v3.43.0_gencode_v39_rna_coord.fa")
@click.option("--t1k_abnormal_unmap_flag", default="True", help="Set if the flag in BAM for the unmapped read-pair is nonconcordant")
@click.option("--t1k_ram", help="GB of RAM to allocate to T1k.")
@click.option("--profile", help="Profile to use for api", default="cavatica")
@click.option("--task_file", help="File to write task ids to", default="task_ids.txt")
@click.option("--override_file", help="File to override input options", default=None)
@click.option("--project", help="Project the app is in, first two '/'s after 'u/' in Cavatica url")
@click.option("--app", help="App name, appid field on Cavaita app page")
def create_task(
	reference_fasta,
	output_basename,
	input_alignment_files,
	input_pe_reads,
	input_pe_mates,
	input_se_reads,
	input_pe_rg_strs,
	input_se_rg_strs,
	cram_reference,
	is_paired_end,
	r1_adapter,
	r2_adapter,
	min_len,
	quality_base,
	quality_cutoff,
	wf_strand_param,
	gtf_anno,
	star_fusion_genome_untar_path,
	read_length_median,
	read_length_stddev,
	samtools_fastq_cores,
	stargenome,
	runthreadn,
	twopassmode,
	alignsjoverhangmin,
	outfiltermismatchnoverlmax,
	outfiltertype,
	outfilterscoreminoverlread,
	outfiltermatchnminoverlread,
	outreadsunmapped,
	limitsjdbinsertnsj,
	outsamstrandfield,
	outfilterintronmotifs,
	alignsoftclipatreferenceends,
	quantmode,
	outsamtype,
	outsamunmapped,
	genomeload,
	chimmainsegmentmultnmax,
	outsamattributes,
	aligninsertionflush,
	alignintronmax,
	alignmatesgapmax,
	alignsjdboverhangmin,
	outfiltermismatchnmax,
	alignsjstitchmismatchnmax,
	alignsplicedmatemaplmin,
	alignsplicedmatemaplminoverlmate,
	chimjunctionoverhangmin,
	chimmultimapnmax,
	chimmultimapscorerange,
	chimnonchimscoredropmin,
	chimoutjunctionformat,
	chimouttype,
	chimscoredropmax,
	chimscorejunctionnongtag,
	chimscoreseparation,
	chimsegmentmin,
	chimsegmentreadgapmax,
	outfiltermultimapnmax,
	peoverlapmmp,
	peoverlapnbasesmin,
	arriba_memory,
	fusiongenome,
	compress_chimeric_junction,
	rnaseqc_gtf,
	kallisto_idx,
	rsemgenome,
	estimate_rspd,
	sample_name,
	annofuse_col_num,
	fusion_annotator_ref,
	rmats_variable_read_length,
	rmats_novel_splice_sites,
	rmats_stat_off,
	rmats_allow_clipping,
	rmats_threads,
	rmats_ram,
	run_t1k,
	hla_rna_ref_seqs,
	hla_rna_gene_coords,
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
					if "reference_fasta" in overrides:
						reference_fasta = line_vals[overrides.index("reference_fasta")]
					if reference_fasta is not None:
						app_inputs["reference_fasta"] = hf.get_file_obj(api, project, reference_fasta)
					if "output_basename" in overrides:
						output_basename = line_vals[overrides.index("output_basename")]
					if output_basename is not None:
						app_inputs["output_basename"] = output_basename
					if "input_alignment_files" in overrides:
						input_alignment_files = line_vals[overrides.index("input_alignment_files")]
					if input_alignment_files is not None:
						input_alignment_files = input_alignment_files.split(",")
						for i in range(len(input_alignment_files)):
							input_alignment_files[i] = hf.get_file_obj(api, project, input_alignment_files[i])
						app_inputs["input_alignment_files"] = input_alignment_files
					if "input_pe_reads" in overrides:
						input_pe_reads = line_vals[overrides.index("input_pe_reads")]
					if input_pe_reads is not None:
						input_pe_reads = input_pe_reads.split(",")
						for i in range(len(input_pe_reads)):
							input_pe_reads[i] = hf.get_file_obj(api, project, input_pe_reads[i])
						app_inputs["input_pe_reads"] = input_pe_reads
					if "input_pe_mates" in overrides:
						input_pe_mates = line_vals[overrides.index("input_pe_mates")]
					if input_pe_mates is not None:
						input_pe_mates = input_pe_mates.split(",")
						for i in range(len(input_pe_mates)):
							input_pe_mates[i] = hf.get_file_obj(api, project, input_pe_mates[i])
						app_inputs["input_pe_mates"] = input_pe_mates
					if "input_se_reads" in overrides:
						input_se_reads = line_vals[overrides.index("input_se_reads")]
					if input_se_reads is not None:
						input_se_reads = input_se_reads.split(",")
						for i in range(len(input_se_reads)):
							input_se_reads[i] = hf.get_file_obj(api, project, input_se_reads[i])
						app_inputs["input_se_reads"] = input_se_reads
					if "input_pe_rg_strs" in overrides:
						input_pe_rg_strs = line_vals[overrides.index("input_pe_rg_strs")]
					if input_pe_rg_strs is not None:
						input_pe_rg_strs = input_pe_rg_strs.split(",")
						for i in range(len(input_pe_rg_strs)):
							input_pe_rg_strs[i] = input_pe_rg_strs[i]
						app_inputs["input_pe_rg_strs"] = input_pe_rg_strs
					if "input_se_rg_strs" in overrides:
						input_se_rg_strs = line_vals[overrides.index("input_se_rg_strs")]
					if input_se_rg_strs is not None:
						input_se_rg_strs = input_se_rg_strs.split(",")
						for i in range(len(input_se_rg_strs)):
							input_se_rg_strs[i] = input_se_rg_strs[i]
						app_inputs["input_se_rg_strs"] = input_se_rg_strs
					if "cram_reference" in overrides:
						cram_reference = line_vals[overrides.index("cram_reference")]
					if cram_reference is not None:
						app_inputs["cram_reference"] = hf.get_file_obj(api, project, cram_reference)
					if "is_paired_end" in overrides:
						is_paired_end = line_vals[overrides.index("is_paired_end")]
					if is_paired_end is not None:
						app_inputs["is_paired_end"] = bool(is_paired_end)
					if "r1_adapter" in overrides:
						r1_adapter = line_vals[overrides.index("r1_adapter")]
					if r1_adapter is not None:
						app_inputs["r1_adapter"] = r1_adapter
					if "r2_adapter" in overrides:
						r2_adapter = line_vals[overrides.index("r2_adapter")]
					if r2_adapter is not None:
						app_inputs["r2_adapter"] = r2_adapter
					if "min_len" in overrides:
						min_len = line_vals[overrides.index("min_len")]
					if min_len is not None:
						app_inputs["min_len"] = int(min_len)
					if "quality_base" in overrides:
						quality_base = line_vals[overrides.index("quality_base")]
					if quality_base is not None:
						app_inputs["quality_base"] = int(quality_base)
					if "quality_cutoff" in overrides:
						quality_cutoff = line_vals[overrides.index("quality_cutoff")]
					if quality_cutoff is not None:
						quality_cutoff = quality_cutoff.split(",")
						for i in range(len(quality_cutoff)):
							quality_cutoff[i] = int(quality_cutoff[i])
						app_inputs["quality_cutoff"] = quality_cutoff
					if "wf_strand_param" in overrides:
						wf_strand_param = line_vals[overrides.index("wf_strand_param")]
					if wf_strand_param is not None:
						app_inputs["wf_strand_param"] = wf_strand_param
					if "gtf_anno" in overrides:
						gtf_anno = line_vals[overrides.index("gtf_anno")]
					if gtf_anno is not None:
						app_inputs["gtf_anno"] = hf.get_file_obj(api, project, gtf_anno)
					if "star_fusion_genome_untar_path" in overrides:
						star_fusion_genome_untar_path = line_vals[overrides.index("star_fusion_genome_untar_path")]
					if star_fusion_genome_untar_path is not None:
						app_inputs["star_fusion_genome_untar_path"] = star_fusion_genome_untar_path
					if "read_length_median" in overrides:
						read_length_median = line_vals[overrides.index("read_length_median")]
					if read_length_median is not None:
						app_inputs["read_length_median"] = int(read_length_median)
					if "read_length_stddev" in overrides:
						read_length_stddev = line_vals[overrides.index("read_length_stddev")]
					if read_length_stddev is not None:
						app_inputs["read_length_stddev"] = float(read_length_stddev)
					if "samtools_fastq_cores" in overrides:
						samtools_fastq_cores = line_vals[overrides.index("samtools_fastq_cores")]
					if samtools_fastq_cores is not None:
						app_inputs["samtools_fastq_cores"] = int(samtools_fastq_cores)
					if "stargenome" in overrides:
						stargenome = line_vals[overrides.index("stargenome")]
					if stargenome is not None:
						app_inputs["STARgenome"] = hf.get_file_obj(api, project, stargenome)
					if "runthreadn" in overrides:
						runthreadn = line_vals[overrides.index("runthreadn")]
					if runthreadn is not None:
						app_inputs["runThreadN"] = int(runthreadn)
					if "twopassmode" in overrides:
						twopassmode = line_vals[overrides.index("twopassmode")]
					if twopassmode is not None:
						app_inputs["twopassMode"] = twopassmode
					if "alignsjoverhangmin" in overrides:
						alignsjoverhangmin = line_vals[overrides.index("alignsjoverhangmin")]
					if alignsjoverhangmin is not None:
						app_inputs["alignSJoverhangMin"] = int(alignsjoverhangmin)
					if "outfiltermismatchnoverlmax" in overrides:
						outfiltermismatchnoverlmax = line_vals[overrides.index("outfiltermismatchnoverlmax")]
					if outfiltermismatchnoverlmax is not None:
						app_inputs["outFilterMismatchNoverLmax"] = float(outfiltermismatchnoverlmax)
					if "outfiltertype" in overrides:
						outfiltertype = line_vals[overrides.index("outfiltertype")]
					if outfiltertype is not None:
						app_inputs["outFilterType"] = outfiltertype
					if "outfilterscoreminoverlread" in overrides:
						outfilterscoreminoverlread = line_vals[overrides.index("outfilterscoreminoverlread")]
					if outfilterscoreminoverlread is not None:
						app_inputs["outFilterScoreMinOverLread"] = float(outfilterscoreminoverlread)
					if "outfiltermatchnminoverlread" in overrides:
						outfiltermatchnminoverlread = line_vals[overrides.index("outfiltermatchnminoverlread")]
					if outfiltermatchnminoverlread is not None:
						app_inputs["outFilterMatchNminOverLread"] = float(outfiltermatchnminoverlread)
					if "outreadsunmapped" in overrides:
						outreadsunmapped = line_vals[overrides.index("outreadsunmapped")]
					if outreadsunmapped is not None:
						app_inputs["outReadsUnmapped"] = outreadsunmapped
					if "limitsjdbinsertnsj" in overrides:
						limitsjdbinsertnsj = line_vals[overrides.index("limitsjdbinsertnsj")]
					if limitsjdbinsertnsj is not None:
						app_inputs["limitSjdbInsertNsj"] = int(limitsjdbinsertnsj)
					if "outsamstrandfield" in overrides:
						outsamstrandfield = line_vals[overrides.index("outsamstrandfield")]
					if outsamstrandfield is not None:
						app_inputs["outSAMstrandField"] = outsamstrandfield
					if "outfilterintronmotifs" in overrides:
						outfilterintronmotifs = line_vals[overrides.index("outfilterintronmotifs")]
					if outfilterintronmotifs is not None:
						app_inputs["outFilterIntronMotifs"] = outfilterintronmotifs
					if "alignsoftclipatreferenceends" in overrides:
						alignsoftclipatreferenceends = line_vals[overrides.index("alignsoftclipatreferenceends")]
					if alignsoftclipatreferenceends is not None:
						app_inputs["alignSoftClipAtReferenceEnds"] = alignsoftclipatreferenceends
					if "quantmode" in overrides:
						quantmode = line_vals[overrides.index("quantmode")]
					if quantmode is not None:
						app_inputs["quantMode"] = quantmode
					if "outsamtype" in overrides:
						outsamtype = line_vals[overrides.index("outsamtype")]
					if outsamtype is not None:
						app_inputs["outSAMtype"] = outsamtype
					if "outsamunmapped" in overrides:
						outsamunmapped = line_vals[overrides.index("outsamunmapped")]
					if outsamunmapped is not None:
						app_inputs["outSAMunmapped"] = outsamunmapped
					if "genomeload" in overrides:
						genomeload = line_vals[overrides.index("genomeload")]
					if genomeload is not None:
						app_inputs["genomeLoad"] = genomeload
					if "chimmainsegmentmultnmax" in overrides:
						chimmainsegmentmultnmax = line_vals[overrides.index("chimmainsegmentmultnmax")]
					if chimmainsegmentmultnmax is not None:
						app_inputs["chimMainSegmentMultNmax"] = int(chimmainsegmentmultnmax)
					if "outsamattributes" in overrides:
						outsamattributes = line_vals[overrides.index("outsamattributes")]
					if outsamattributes is not None:
						app_inputs["outSAMattributes"] = outsamattributes
					if "aligninsertionflush" in overrides:
						aligninsertionflush = line_vals[overrides.index("aligninsertionflush")]
					if aligninsertionflush is not None:
						app_inputs["alignInsertionFlush"] = aligninsertionflush
					if "alignintronmax" in overrides:
						alignintronmax = line_vals[overrides.index("alignintronmax")]
					if alignintronmax is not None:
						app_inputs["alignIntronMax"] = int(alignintronmax)
					if "alignmatesgapmax" in overrides:
						alignmatesgapmax = line_vals[overrides.index("alignmatesgapmax")]
					if alignmatesgapmax is not None:
						app_inputs["alignMatesGapMax"] = int(alignmatesgapmax)
					if "alignsjdboverhangmin" in overrides:
						alignsjdboverhangmin = line_vals[overrides.index("alignsjdboverhangmin")]
					if alignsjdboverhangmin is not None:
						app_inputs["alignSJDBoverhangMin"] = int(alignsjdboverhangmin)
					if "outfiltermismatchnmax" in overrides:
						outfiltermismatchnmax = line_vals[overrides.index("outfiltermismatchnmax")]
					if outfiltermismatchnmax is not None:
						app_inputs["outFilterMismatchNmax"] = int(outfiltermismatchnmax)
					if "alignsjstitchmismatchnmax" in overrides:
						alignsjstitchmismatchnmax = line_vals[overrides.index("alignsjstitchmismatchnmax")]
					if alignsjstitchmismatchnmax is not None:
						app_inputs["alignSJstitchMismatchNmax"] = alignsjstitchmismatchnmax
					if "alignsplicedmatemaplmin" in overrides:
						alignsplicedmatemaplmin = line_vals[overrides.index("alignsplicedmatemaplmin")]
					if alignsplicedmatemaplmin is not None:
						app_inputs["alignSplicedMateMapLmin"] = int(alignsplicedmatemaplmin)
					if "alignsplicedmatemaplminoverlmate" in overrides:
						alignsplicedmatemaplminoverlmate = line_vals[overrides.index("alignsplicedmatemaplminoverlmate")]
					if alignsplicedmatemaplminoverlmate is not None:
						app_inputs["alignSplicedMateMapLminOverLmate"] = float(alignsplicedmatemaplminoverlmate)
					if "chimjunctionoverhangmin" in overrides:
						chimjunctionoverhangmin = line_vals[overrides.index("chimjunctionoverhangmin")]
					if chimjunctionoverhangmin is not None:
						app_inputs["chimJunctionOverhangMin"] = int(chimjunctionoverhangmin)
					if "chimmultimapnmax" in overrides:
						chimmultimapnmax = line_vals[overrides.index("chimmultimapnmax")]
					if chimmultimapnmax is not None:
						app_inputs["chimMultimapNmax"] = int(chimmultimapnmax)
					if "chimmultimapscorerange" in overrides:
						chimmultimapscorerange = line_vals[overrides.index("chimmultimapscorerange")]
					if chimmultimapscorerange is not None:
						app_inputs["chimMultimapScoreRange"] = int(chimmultimapscorerange)
					if "chimnonchimscoredropmin" in overrides:
						chimnonchimscoredropmin = line_vals[overrides.index("chimnonchimscoredropmin")]
					if chimnonchimscoredropmin is not None:
						app_inputs["chimNonchimScoreDropMin"] = int(chimnonchimscoredropmin)
					if "chimoutjunctionformat" in overrides:
						chimoutjunctionformat = line_vals[overrides.index("chimoutjunctionformat")]
					if chimoutjunctionformat is not None:
						app_inputs["chimOutJunctionFormat"] = int(chimoutjunctionformat)
					if "chimouttype" in overrides:
						chimouttype = line_vals[overrides.index("chimouttype")]
					if chimouttype is not None:
						app_inputs["chimOutType"] = chimouttype
					if "chimscoredropmax" in overrides:
						chimscoredropmax = line_vals[overrides.index("chimscoredropmax")]
					if chimscoredropmax is not None:
						app_inputs["chimScoreDropMax"] = int(chimscoredropmax)
					if "chimscorejunctionnongtag" in overrides:
						chimscorejunctionnongtag = line_vals[overrides.index("chimscorejunctionnongtag")]
					if chimscorejunctionnongtag is not None:
						app_inputs["chimScoreJunctionNonGTAG"] = int(chimscorejunctionnongtag)
					if "chimscoreseparation" in overrides:
						chimscoreseparation = line_vals[overrides.index("chimscoreseparation")]
					if chimscoreseparation is not None:
						app_inputs["chimScoreSeparation"] = int(chimscoreseparation)
					if "chimsegmentmin" in overrides:
						chimsegmentmin = line_vals[overrides.index("chimsegmentmin")]
					if chimsegmentmin is not None:
						app_inputs["chimSegmentMin"] = int(chimsegmentmin)
					if "chimsegmentreadgapmax" in overrides:
						chimsegmentreadgapmax = line_vals[overrides.index("chimsegmentreadgapmax")]
					if chimsegmentreadgapmax is not None:
						app_inputs["chimSegmentReadGapMax"] = int(chimsegmentreadgapmax)
					if "outfiltermultimapnmax" in overrides:
						outfiltermultimapnmax = line_vals[overrides.index("outfiltermultimapnmax")]
					if outfiltermultimapnmax is not None:
						app_inputs["outFilterMultimapNmax"] = int(outfiltermultimapnmax)
					if "peoverlapmmp" in overrides:
						peoverlapmmp = line_vals[overrides.index("peoverlapmmp")]
					if peoverlapmmp is not None:
						app_inputs["peOverlapMMp"] = float(peoverlapmmp)
					if "peoverlapnbasesmin" in overrides:
						peoverlapnbasesmin = line_vals[overrides.index("peoverlapnbasesmin")]
					if peoverlapnbasesmin is not None:
						app_inputs["peOverlapNbasesMin"] = int(peoverlapnbasesmin)
					if "arriba_memory" in overrides:
						arriba_memory = line_vals[overrides.index("arriba_memory")]
					if arriba_memory is not None:
						app_inputs["arriba_memory"] = int(arriba_memory)
					if "fusiongenome" in overrides:
						fusiongenome = line_vals[overrides.index("fusiongenome")]
					if fusiongenome is not None:
						app_inputs["FusionGenome"] = hf.get_file_obj(api, project, fusiongenome)
					if "compress_chimeric_junction" in overrides:
						compress_chimeric_junction = line_vals[overrides.index("compress_chimeric_junction")]
					if compress_chimeric_junction is not None:
						app_inputs["compress_chimeric_junction"] = bool(compress_chimeric_junction)
					if "rnaseqc_gtf" in overrides:
						rnaseqc_gtf = line_vals[overrides.index("rnaseqc_gtf")]
					if rnaseqc_gtf is not None:
						app_inputs["RNAseQC_GTF"] = hf.get_file_obj(api, project, rnaseqc_gtf)
					if "kallisto_idx" in overrides:
						kallisto_idx = line_vals[overrides.index("kallisto_idx")]
					if kallisto_idx is not None:
						app_inputs["kallisto_idx"] = hf.get_file_obj(api, project, kallisto_idx)
					if "rsemgenome" in overrides:
						rsemgenome = line_vals[overrides.index("rsemgenome")]
					if rsemgenome is not None:
						app_inputs["RSEMgenome"] = hf.get_file_obj(api, project, rsemgenome)
					if "estimate_rspd" in overrides:
						estimate_rspd = line_vals[overrides.index("estimate_rspd")]
					if estimate_rspd is not None:
						app_inputs["estimate_rspd"] = bool(estimate_rspd)
					if "sample_name" in overrides:
						sample_name = line_vals[overrides.index("sample_name")]
					if sample_name is not None:
						app_inputs["sample_name"] = sample_name
					if "annofuse_col_num" in overrides:
						annofuse_col_num = line_vals[overrides.index("annofuse_col_num")]
					if annofuse_col_num is not None:
						app_inputs["annofuse_col_num"] = int(annofuse_col_num)
					if "fusion_annotator_ref" in overrides:
						fusion_annotator_ref = line_vals[overrides.index("fusion_annotator_ref")]
					if fusion_annotator_ref is not None:
						app_inputs["fusion_annotator_ref"] = hf.get_file_obj(api, project, fusion_annotator_ref)
					if "rmats_variable_read_length" in overrides:
						rmats_variable_read_length = line_vals[overrides.index("rmats_variable_read_length")]
					if rmats_variable_read_length is not None:
						app_inputs["rmats_variable_read_length"] = bool(rmats_variable_read_length)
					if "rmats_novel_splice_sites" in overrides:
						rmats_novel_splice_sites = line_vals[overrides.index("rmats_novel_splice_sites")]
					if rmats_novel_splice_sites is not None:
						app_inputs["rmats_novel_splice_sites"] = bool(rmats_novel_splice_sites)
					if "rmats_stat_off" in overrides:
						rmats_stat_off = line_vals[overrides.index("rmats_stat_off")]
					if rmats_stat_off is not None:
						app_inputs["rmats_stat_off"] = bool(rmats_stat_off)
					if "rmats_allow_clipping" in overrides:
						rmats_allow_clipping = line_vals[overrides.index("rmats_allow_clipping")]
					if rmats_allow_clipping is not None:
						app_inputs["rmats_allow_clipping"] = bool(rmats_allow_clipping)
					if "rmats_threads" in overrides:
						rmats_threads = line_vals[overrides.index("rmats_threads")]
					if rmats_threads is not None:
						app_inputs["rmats_threads"] = int(rmats_threads)
					if "rmats_ram" in overrides:
						rmats_ram = line_vals[overrides.index("rmats_ram")]
					if rmats_ram is not None:
						app_inputs["rmats_ram"] = int(rmats_ram)
					if "run_t1k" in overrides:
						run_t1k = line_vals[overrides.index("run_t1k")]
					if run_t1k is not None:
						app_inputs["run_t1k"] = bool(run_t1k)
					if "hla_rna_ref_seqs" in overrides:
						hla_rna_ref_seqs = line_vals[overrides.index("hla_rna_ref_seqs")]
					if hla_rna_ref_seqs is not None:
						app_inputs["hla_rna_ref_seqs"] = hf.get_file_obj(api, project, hla_rna_ref_seqs)
					if "hla_rna_gene_coords" in overrides:
						hla_rna_gene_coords = line_vals[overrides.index("hla_rna_gene_coords")]
					if hla_rna_gene_coords is not None:
						app_inputs["hla_rna_gene_coords"] = hf.get_file_obj(api, project, hla_rna_gene_coords)
					if "t1k_abnormal_unmap_flag" in overrides:
						t1k_abnormal_unmap_flag = line_vals[overrides.index("t1k_abnormal_unmap_flag")]
					if t1k_abnormal_unmap_flag is not None:
						app_inputs["t1k_abnormal_unmap_flag"] = bool(t1k_abnormal_unmap_flag)
					if "t1k_ram" in overrides:
						t1k_ram = line_vals[overrides.index("t1k_ram")]
					if t1k_ram is not None:
						app_inputs["t1k_ram"] = int(t1k_ram)
					new_task = api.tasks.create(
						name="kfdrc_RNAseq_workflow",
						project=project,
						app=app,
						inputs = app_inputs
					)
					time.sleep(15)
					print(new_task.name, new_task.status, new_task.id)
					task_ids.append(new_task.id)
				line_num += 1
	else:
		app_inputs = {}
		if "reference_fasta" in overrides:
			reference_fasta = line_vals[overrides.index("reference_fasta")]
		if reference_fasta is not None:
			app_inputs["reference_fasta"] = hf.get_file_obj(api, project, reference_fasta)
		if "output_basename" in overrides:
			output_basename = line_vals[overrides.index("output_basename")]
		if output_basename is not None:
			app_inputs["output_basename"] = output_basename
		if "input_alignment_files" in overrides:
			input_alignment_files = line_vals[overrides.index("input_alignment_files")]
		if input_alignment_files is not None:
			input_alignment_files = input_alignment_files.split(",")
			for i in range(len(input_alignment_files)):
				input_alignment_files[i] = hf.get_file_obj(api, project, input_alignment_files[i])
			app_inputs["input_alignment_files"] = input_alignment_files
		if "input_pe_reads" in overrides:
			input_pe_reads = line_vals[overrides.index("input_pe_reads")]
		if input_pe_reads is not None:
			input_pe_reads = input_pe_reads.split(",")
			for i in range(len(input_pe_reads)):
				input_pe_reads[i] = hf.get_file_obj(api, project, input_pe_reads[i])
			app_inputs["input_pe_reads"] = input_pe_reads
		if "input_pe_mates" in overrides:
			input_pe_mates = line_vals[overrides.index("input_pe_mates")]
		if input_pe_mates is not None:
			input_pe_mates = input_pe_mates.split(",")
			for i in range(len(input_pe_mates)):
				input_pe_mates[i] = hf.get_file_obj(api, project, input_pe_mates[i])
			app_inputs["input_pe_mates"] = input_pe_mates
		if "input_se_reads" in overrides:
			input_se_reads = line_vals[overrides.index("input_se_reads")]
		if input_se_reads is not None:
			input_se_reads = input_se_reads.split(",")
			for i in range(len(input_se_reads)):
				input_se_reads[i] = hf.get_file_obj(api, project, input_se_reads[i])
			app_inputs["input_se_reads"] = input_se_reads
		if "input_pe_rg_strs" in overrides:
			input_pe_rg_strs = line_vals[overrides.index("input_pe_rg_strs")]
		if input_pe_rg_strs is not None:
			input_pe_rg_strs = input_pe_rg_strs.split(",")
			for i in range(len(input_pe_rg_strs)):
				input_pe_rg_strs[i] = input_pe_rg_strs[i]
			app_inputs["input_pe_rg_strs"] = input_pe_rg_strs
		if "input_se_rg_strs" in overrides:
			input_se_rg_strs = line_vals[overrides.index("input_se_rg_strs")]
		if input_se_rg_strs is not None:
			input_se_rg_strs = input_se_rg_strs.split(",")
			for i in range(len(input_se_rg_strs)):
				input_se_rg_strs[i] = input_se_rg_strs[i]
			app_inputs["input_se_rg_strs"] = input_se_rg_strs
		if "cram_reference" in overrides:
			cram_reference = line_vals[overrides.index("cram_reference")]
		if cram_reference is not None:
			app_inputs["cram_reference"] = hf.get_file_obj(api, project, cram_reference)
		if "is_paired_end" in overrides:
			is_paired_end = line_vals[overrides.index("is_paired_end")]
		if is_paired_end is not None:
			app_inputs["is_paired_end"] = bool(is_paired_end)
		if "r1_adapter" in overrides:
			r1_adapter = line_vals[overrides.index("r1_adapter")]
		if r1_adapter is not None:
			app_inputs["r1_adapter"] = r1_adapter
		if "r2_adapter" in overrides:
			r2_adapter = line_vals[overrides.index("r2_adapter")]
		if r2_adapter is not None:
			app_inputs["r2_adapter"] = r2_adapter
		if "min_len" in overrides:
			min_len = line_vals[overrides.index("min_len")]
		if min_len is not None:
			app_inputs["min_len"] = int(min_len)
		if "quality_base" in overrides:
			quality_base = line_vals[overrides.index("quality_base")]
		if quality_base is not None:
			app_inputs["quality_base"] = int(quality_base)
		if "quality_cutoff" in overrides:
			quality_cutoff = line_vals[overrides.index("quality_cutoff")]
		if quality_cutoff is not None:
			quality_cutoff = quality_cutoff.split(",")
			for i in range(len(quality_cutoff)):
				quality_cutoff[i] = int(quality_cutoff[i])
			app_inputs["quality_cutoff"] = quality_cutoff
		if "wf_strand_param" in overrides:
			wf_strand_param = line_vals[overrides.index("wf_strand_param")]
		if wf_strand_param is not None:
			app_inputs["wf_strand_param"] = wf_strand_param
		if "gtf_anno" in overrides:
			gtf_anno = line_vals[overrides.index("gtf_anno")]
		if gtf_anno is not None:
			app_inputs["gtf_anno"] = hf.get_file_obj(api, project, gtf_anno)
		if "star_fusion_genome_untar_path" in overrides:
			star_fusion_genome_untar_path = line_vals[overrides.index("star_fusion_genome_untar_path")]
		if star_fusion_genome_untar_path is not None:
			app_inputs["star_fusion_genome_untar_path"] = star_fusion_genome_untar_path
		if "read_length_median" in overrides:
			read_length_median = line_vals[overrides.index("read_length_median")]
		if read_length_median is not None:
			app_inputs["read_length_median"] = int(read_length_median)
		if "read_length_stddev" in overrides:
			read_length_stddev = line_vals[overrides.index("read_length_stddev")]
		if read_length_stddev is not None:
			app_inputs["read_length_stddev"] = float(read_length_stddev)
		if "samtools_fastq_cores" in overrides:
			samtools_fastq_cores = line_vals[overrides.index("samtools_fastq_cores")]
		if samtools_fastq_cores is not None:
			app_inputs["samtools_fastq_cores"] = int(samtools_fastq_cores)
		if "stargenome" in overrides:
			stargenome = line_vals[overrides.index("stargenome")]
		if stargenome is not None:
			app_inputs["STARgenome"] = hf.get_file_obj(api, project, stargenome)
		if "runthreadn" in overrides:
			runthreadn = line_vals[overrides.index("runthreadn")]
		if runthreadn is not None:
			app_inputs["runThreadN"] = int(runthreadn)
		if "twopassmode" in overrides:
			twopassmode = line_vals[overrides.index("twopassmode")]
		if twopassmode is not None:
			app_inputs["twopassMode"] = twopassmode
		if "alignsjoverhangmin" in overrides:
			alignsjoverhangmin = line_vals[overrides.index("alignsjoverhangmin")]
		if alignsjoverhangmin is not None:
			app_inputs["alignSJoverhangMin"] = int(alignsjoverhangmin)
		if "outfiltermismatchnoverlmax" in overrides:
			outfiltermismatchnoverlmax = line_vals[overrides.index("outfiltermismatchnoverlmax")]
		if outfiltermismatchnoverlmax is not None:
			app_inputs["outFilterMismatchNoverLmax"] = float(outfiltermismatchnoverlmax)
		if "outfiltertype" in overrides:
			outfiltertype = line_vals[overrides.index("outfiltertype")]
		if outfiltertype is not None:
			app_inputs["outFilterType"] = outfiltertype
		if "outfilterscoreminoverlread" in overrides:
			outfilterscoreminoverlread = line_vals[overrides.index("outfilterscoreminoverlread")]
		if outfilterscoreminoverlread is not None:
			app_inputs["outFilterScoreMinOverLread"] = float(outfilterscoreminoverlread)
		if "outfiltermatchnminoverlread" in overrides:
			outfiltermatchnminoverlread = line_vals[overrides.index("outfiltermatchnminoverlread")]
		if outfiltermatchnminoverlread is not None:
			app_inputs["outFilterMatchNminOverLread"] = float(outfiltermatchnminoverlread)
		if "outreadsunmapped" in overrides:
			outreadsunmapped = line_vals[overrides.index("outreadsunmapped")]
		if outreadsunmapped is not None:
			app_inputs["outReadsUnmapped"] = outreadsunmapped
		if "limitsjdbinsertnsj" in overrides:
			limitsjdbinsertnsj = line_vals[overrides.index("limitsjdbinsertnsj")]
		if limitsjdbinsertnsj is not None:
			app_inputs["limitSjdbInsertNsj"] = int(limitsjdbinsertnsj)
		if "outsamstrandfield" in overrides:
			outsamstrandfield = line_vals[overrides.index("outsamstrandfield")]
		if outsamstrandfield is not None:
			app_inputs["outSAMstrandField"] = outsamstrandfield
		if "outfilterintronmotifs" in overrides:
			outfilterintronmotifs = line_vals[overrides.index("outfilterintronmotifs")]
		if outfilterintronmotifs is not None:
			app_inputs["outFilterIntronMotifs"] = outfilterintronmotifs
		if "alignsoftclipatreferenceends" in overrides:
			alignsoftclipatreferenceends = line_vals[overrides.index("alignsoftclipatreferenceends")]
		if alignsoftclipatreferenceends is not None:
			app_inputs["alignSoftClipAtReferenceEnds"] = alignsoftclipatreferenceends
		if "quantmode" in overrides:
			quantmode = line_vals[overrides.index("quantmode")]
		if quantmode is not None:
			app_inputs["quantMode"] = quantmode
		if "outsamtype" in overrides:
			outsamtype = line_vals[overrides.index("outsamtype")]
		if outsamtype is not None:
			app_inputs["outSAMtype"] = outsamtype
		if "outsamunmapped" in overrides:
			outsamunmapped = line_vals[overrides.index("outsamunmapped")]
		if outsamunmapped is not None:
			app_inputs["outSAMunmapped"] = outsamunmapped
		if "genomeload" in overrides:
			genomeload = line_vals[overrides.index("genomeload")]
		if genomeload is not None:
			app_inputs["genomeLoad"] = genomeload
		if "chimmainsegmentmultnmax" in overrides:
			chimmainsegmentmultnmax = line_vals[overrides.index("chimmainsegmentmultnmax")]
		if chimmainsegmentmultnmax is not None:
			app_inputs["chimMainSegmentMultNmax"] = int(chimmainsegmentmultnmax)
		if "outsamattributes" in overrides:
			outsamattributes = line_vals[overrides.index("outsamattributes")]
		if outsamattributes is not None:
			app_inputs["outSAMattributes"] = outsamattributes
		if "aligninsertionflush" in overrides:
			aligninsertionflush = line_vals[overrides.index("aligninsertionflush")]
		if aligninsertionflush is not None:
			app_inputs["alignInsertionFlush"] = aligninsertionflush
		if "alignintronmax" in overrides:
			alignintronmax = line_vals[overrides.index("alignintronmax")]
		if alignintronmax is not None:
			app_inputs["alignIntronMax"] = int(alignintronmax)
		if "alignmatesgapmax" in overrides:
			alignmatesgapmax = line_vals[overrides.index("alignmatesgapmax")]
		if alignmatesgapmax is not None:
			app_inputs["alignMatesGapMax"] = int(alignmatesgapmax)
		if "alignsjdboverhangmin" in overrides:
			alignsjdboverhangmin = line_vals[overrides.index("alignsjdboverhangmin")]
		if alignsjdboverhangmin is not None:
			app_inputs["alignSJDBoverhangMin"] = int(alignsjdboverhangmin)
		if "outfiltermismatchnmax" in overrides:
			outfiltermismatchnmax = line_vals[overrides.index("outfiltermismatchnmax")]
		if outfiltermismatchnmax is not None:
			app_inputs["outFilterMismatchNmax"] = int(outfiltermismatchnmax)
		if "alignsjstitchmismatchnmax" in overrides:
			alignsjstitchmismatchnmax = line_vals[overrides.index("alignsjstitchmismatchnmax")]
		if alignsjstitchmismatchnmax is not None:
			app_inputs["alignSJstitchMismatchNmax"] = alignsjstitchmismatchnmax
		if "alignsplicedmatemaplmin" in overrides:
			alignsplicedmatemaplmin = line_vals[overrides.index("alignsplicedmatemaplmin")]
		if alignsplicedmatemaplmin is not None:
			app_inputs["alignSplicedMateMapLmin"] = int(alignsplicedmatemaplmin)
		if "alignsplicedmatemaplminoverlmate" in overrides:
			alignsplicedmatemaplminoverlmate = line_vals[overrides.index("alignsplicedmatemaplminoverlmate")]
		if alignsplicedmatemaplminoverlmate is not None:
			app_inputs["alignSplicedMateMapLminOverLmate"] = float(alignsplicedmatemaplminoverlmate)
		if "chimjunctionoverhangmin" in overrides:
			chimjunctionoverhangmin = line_vals[overrides.index("chimjunctionoverhangmin")]
		if chimjunctionoverhangmin is not None:
			app_inputs["chimJunctionOverhangMin"] = int(chimjunctionoverhangmin)
		if "chimmultimapnmax" in overrides:
			chimmultimapnmax = line_vals[overrides.index("chimmultimapnmax")]
		if chimmultimapnmax is not None:
			app_inputs["chimMultimapNmax"] = int(chimmultimapnmax)
		if "chimmultimapscorerange" in overrides:
			chimmultimapscorerange = line_vals[overrides.index("chimmultimapscorerange")]
		if chimmultimapscorerange is not None:
			app_inputs["chimMultimapScoreRange"] = int(chimmultimapscorerange)
		if "chimnonchimscoredropmin" in overrides:
			chimnonchimscoredropmin = line_vals[overrides.index("chimnonchimscoredropmin")]
		if chimnonchimscoredropmin is not None:
			app_inputs["chimNonchimScoreDropMin"] = int(chimnonchimscoredropmin)
		if "chimoutjunctionformat" in overrides:
			chimoutjunctionformat = line_vals[overrides.index("chimoutjunctionformat")]
		if chimoutjunctionformat is not None:
			app_inputs["chimOutJunctionFormat"] = int(chimoutjunctionformat)
		if "chimouttype" in overrides:
			chimouttype = line_vals[overrides.index("chimouttype")]
		if chimouttype is not None:
			app_inputs["chimOutType"] = chimouttype
		if "chimscoredropmax" in overrides:
			chimscoredropmax = line_vals[overrides.index("chimscoredropmax")]
		if chimscoredropmax is not None:
			app_inputs["chimScoreDropMax"] = int(chimscoredropmax)
		if "chimscorejunctionnongtag" in overrides:
			chimscorejunctionnongtag = line_vals[overrides.index("chimscorejunctionnongtag")]
		if chimscorejunctionnongtag is not None:
			app_inputs["chimScoreJunctionNonGTAG"] = int(chimscorejunctionnongtag)
		if "chimscoreseparation" in overrides:
			chimscoreseparation = line_vals[overrides.index("chimscoreseparation")]
		if chimscoreseparation is not None:
			app_inputs["chimScoreSeparation"] = int(chimscoreseparation)
		if "chimsegmentmin" in overrides:
			chimsegmentmin = line_vals[overrides.index("chimsegmentmin")]
		if chimsegmentmin is not None:
			app_inputs["chimSegmentMin"] = int(chimsegmentmin)
		if "chimsegmentreadgapmax" in overrides:
			chimsegmentreadgapmax = line_vals[overrides.index("chimsegmentreadgapmax")]
		if chimsegmentreadgapmax is not None:
			app_inputs["chimSegmentReadGapMax"] = int(chimsegmentreadgapmax)
		if "outfiltermultimapnmax" in overrides:
			outfiltermultimapnmax = line_vals[overrides.index("outfiltermultimapnmax")]
		if outfiltermultimapnmax is not None:
			app_inputs["outFilterMultimapNmax"] = int(outfiltermultimapnmax)
		if "peoverlapmmp" in overrides:
			peoverlapmmp = line_vals[overrides.index("peoverlapmmp")]
		if peoverlapmmp is not None:
			app_inputs["peOverlapMMp"] = float(peoverlapmmp)
		if "peoverlapnbasesmin" in overrides:
			peoverlapnbasesmin = line_vals[overrides.index("peoverlapnbasesmin")]
		if peoverlapnbasesmin is not None:
			app_inputs["peOverlapNbasesMin"] = int(peoverlapnbasesmin)
		if "arriba_memory" in overrides:
			arriba_memory = line_vals[overrides.index("arriba_memory")]
		if arriba_memory is not None:
			app_inputs["arriba_memory"] = int(arriba_memory)
		if "fusiongenome" in overrides:
			fusiongenome = line_vals[overrides.index("fusiongenome")]
		if fusiongenome is not None:
			app_inputs["FusionGenome"] = hf.get_file_obj(api, project, fusiongenome)
		if "compress_chimeric_junction" in overrides:
			compress_chimeric_junction = line_vals[overrides.index("compress_chimeric_junction")]
		if compress_chimeric_junction is not None:
			app_inputs["compress_chimeric_junction"] = bool(compress_chimeric_junction)
		if "rnaseqc_gtf" in overrides:
			rnaseqc_gtf = line_vals[overrides.index("rnaseqc_gtf")]
		if rnaseqc_gtf is not None:
			app_inputs["RNAseQC_GTF"] = hf.get_file_obj(api, project, rnaseqc_gtf)
		if "kallisto_idx" in overrides:
			kallisto_idx = line_vals[overrides.index("kallisto_idx")]
		if kallisto_idx is not None:
			app_inputs["kallisto_idx"] = hf.get_file_obj(api, project, kallisto_idx)
		if "rsemgenome" in overrides:
			rsemgenome = line_vals[overrides.index("rsemgenome")]
		if rsemgenome is not None:
			app_inputs["RSEMgenome"] = hf.get_file_obj(api, project, rsemgenome)
		if "estimate_rspd" in overrides:
			estimate_rspd = line_vals[overrides.index("estimate_rspd")]
		if estimate_rspd is not None:
			app_inputs["estimate_rspd"] = bool(estimate_rspd)
		if "sample_name" in overrides:
			sample_name = line_vals[overrides.index("sample_name")]
		if sample_name is not None:
			app_inputs["sample_name"] = sample_name
		if "annofuse_col_num" in overrides:
			annofuse_col_num = line_vals[overrides.index("annofuse_col_num")]
		if annofuse_col_num is not None:
			app_inputs["annofuse_col_num"] = int(annofuse_col_num)
		if "fusion_annotator_ref" in overrides:
			fusion_annotator_ref = line_vals[overrides.index("fusion_annotator_ref")]
		if fusion_annotator_ref is not None:
			app_inputs["fusion_annotator_ref"] = hf.get_file_obj(api, project, fusion_annotator_ref)
		if "rmats_variable_read_length" in overrides:
			rmats_variable_read_length = line_vals[overrides.index("rmats_variable_read_length")]
		if rmats_variable_read_length is not None:
			app_inputs["rmats_variable_read_length"] = bool(rmats_variable_read_length)
		if "rmats_novel_splice_sites" in overrides:
			rmats_novel_splice_sites = line_vals[overrides.index("rmats_novel_splice_sites")]
		if rmats_novel_splice_sites is not None:
			app_inputs["rmats_novel_splice_sites"] = bool(rmats_novel_splice_sites)
		if "rmats_stat_off" in overrides:
			rmats_stat_off = line_vals[overrides.index("rmats_stat_off")]
		if rmats_stat_off is not None:
			app_inputs["rmats_stat_off"] = bool(rmats_stat_off)
		if "rmats_allow_clipping" in overrides:
			rmats_allow_clipping = line_vals[overrides.index("rmats_allow_clipping")]
		if rmats_allow_clipping is not None:
			app_inputs["rmats_allow_clipping"] = bool(rmats_allow_clipping)
		if "rmats_threads" in overrides:
			rmats_threads = line_vals[overrides.index("rmats_threads")]
		if rmats_threads is not None:
			app_inputs["rmats_threads"] = int(rmats_threads)
		if "rmats_ram" in overrides:
			rmats_ram = line_vals[overrides.index("rmats_ram")]
		if rmats_ram is not None:
			app_inputs["rmats_ram"] = int(rmats_ram)
		if "run_t1k" in overrides:
			run_t1k = line_vals[overrides.index("run_t1k")]
		if run_t1k is not None:
			app_inputs["run_t1k"] = bool(run_t1k)
		if "hla_rna_ref_seqs" in overrides:
			hla_rna_ref_seqs = line_vals[overrides.index("hla_rna_ref_seqs")]
		if hla_rna_ref_seqs is not None:
			app_inputs["hla_rna_ref_seqs"] = hf.get_file_obj(api, project, hla_rna_ref_seqs)
		if "hla_rna_gene_coords" in overrides:
			hla_rna_gene_coords = line_vals[overrides.index("hla_rna_gene_coords")]
		if hla_rna_gene_coords is not None:
			app_inputs["hla_rna_gene_coords"] = hf.get_file_obj(api, project, hla_rna_gene_coords)
		if "t1k_abnormal_unmap_flag" in overrides:
			t1k_abnormal_unmap_flag = line_vals[overrides.index("t1k_abnormal_unmap_flag")]
		if t1k_abnormal_unmap_flag is not None:
			app_inputs["t1k_abnormal_unmap_flag"] = bool(t1k_abnormal_unmap_flag)
		if "t1k_ram" in overrides:
			t1k_ram = line_vals[overrides.index("t1k_ram")]
		if t1k_ram is not None:
			app_inputs["t1k_ram"] = int(t1k_ram)
		new_task = api.tasks.create(
			name="kfdrc_RNAseq_workflow",
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
