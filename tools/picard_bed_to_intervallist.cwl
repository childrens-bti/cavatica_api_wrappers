cwlVersion: v1.0
class: CommandLineTool
id: picard_bed2intervallist
requirements:
  - class: ShellCommandRequirement
  - class: InlineJavascriptRequirement
  - class: DockerRequirement
    dockerPull: 'pgc-images.sbgenomics.com/d3b-bixu/picard:2.18.9R'
  - class: ResourceRequirement
    ramMin: 2000


baseCommand: [java, -Xmx2000m, -jar, /picard.jar, BedToIntervalList]
arguments:
  - position: 1
    shellQuote: false
    valueFrom: >-
      I=$(inputs.bed.path)
      O=$(inputs.interval_list_base).interval_list
      SD=$(inputs.sequence_dict.path)

inputs:
  interval_list_base: { type: string, doc: "Interval list basename"}
  bed: {type: 'File', doc: "Input bed file"}
  sequence_dict: {type: 'File', doc: "Input sequence dict file"}
outputs:
  output:
    type: File
    outputBinding:
      glob: '*.interval_list'
