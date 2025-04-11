cwlVersion: v1.2
class: CommandLineTool
id: pad_Bed
doc: "Pad a bed file using bedtools slop"
requirements:
  - class: ShellCommandRequirement
  - class: InlineJavascriptRequirement
  - class: ResourceRequirement
    ramMin: 8000
    coresMin: 4
  - class: DockerRequirement
    dockerPull: 'pgc-images.sbgenomics.com/d3b-bixu/bed_tools:bedopsv2.4.36_plus_bedtools'

baseCommand: ["/bin/bash", "-c"]
arguments:
  - position: 0
    shellQuote: false
    valueFrom: >-
      set -eo pipefail &&
      bedtools slop -i $(inputs.input_bed.path) -g $(inputs.input_size.path)

  - position: 99
    shellQuote: false
    valueFrom: >
      > $(inputs.input_bed.basename)_padded.bed

inputs:
  input_bed: {type: File}
  input_size: {type: File, doc: "Input genome size file"}
  pad_both: {type: 'int?', inputBinding: {position: 2, prefix: "-b"}, doc: "Increase the BED/GFF/VCF entry by the same number base pairs in each direction. Integer."}
  pad_left: {type: 'int?', inputBinding: {position: 2, prefix: "-l"}, doc: "The number of base pairs to subtract from the start coordinate. Integer."}
  pad_right: {type: 'int?', inputBinding: {position: 2, prefix: "-r"}, doc: "The number of base pairs to add to the end coordinate. Integer."}
  stranded: {type: 'boolean?', inputBinding: {position: 2, prefix: "-s"}, doc: "Define -l and -r based on strand. For example. if used, -l 500 for a negative-stranded feature, it will add 500 bp to the end coordinate."}
  percent: {type: 'boolean?', inputBinding: {position: 2, prefix: "-pct"}, doc: "Define -l and -r as a fraction of the feature’s length. E.g. if used on a 1000bp feature, -l 0.50, will add 500 bp “upstream”. Default = false."}
  header: {type: 'boolean?', inputBinding: {position: 2, prefix: "-header"}, doc: "Print the header from the input file prior to results."}

outputs:
  padded_bed:
    type: File
    outputBinding:
      glob: '*.bed'
