#!/usr/bin/env bash
set -euo pipefail

module load samtools/1.17-4rtlp3g

INPUT_DIR="${1:-.}"
OUTPUT_DIR="${2:-single_rg_bams}"
THREADS="${3:-4}"

mkdir -p "${OUTPUT_DIR}"

REPORT="${OUTPUT_DIR}/read_group_cleanup_report.txt"
rm -f "${REPORT}"

shopt -s nullglob globstar

for bam in "${INPUT_DIR}"/**/*.bam; do
  [ -e "$bam" ] || continue

  # Get the read-group IDs from the BAM header.
  mapfile -t rgs < <(
    samtools view -H "$bam" |
      awk -F'\t' '$1 == "@RG" {for (i = 2; i <= NF; i++) if ($i ~ /^ID:/) {sub(/^ID:/, "", $i); print $i}}'
  )

  sample=$(basename "$bam" .bam)
  rg_count="${#rgs[@]}"

  if [[ "${rg_count}" -eq 1 ]]; then
    echo "${sample}: skipped (one read group: ${rgs[0]})" | tee -a "${REPORT}"

  elif [[ "${rg_count}" -eq 2 ]]; then
    # Keep the _1 read group. If there is no _1, keep the first one.
    keep_rg="${rgs[0]}"
    for rg in "${rgs[@]}"; do
      if [[ "$rg" == *_1 ]]; then
        keep_rg="$rg"
      fi
    done

    output_bam="${OUTPUT_DIR}/${sample}.singleRG.bam"
    echo "${sample}: keeping ${keep_rg}" | tee -a "${REPORT}"

    samtools view -@ "${THREADS}" -b -r "${keep_rg}" "$bam" \
      -o "${output_bam}"
    samtools index -@ "${THREADS}" "${output_bam}"

  else
    echo "${sample}: skipped (${rg_count} read groups)" | tee -a "${REPORT}"
  fi
done

echo >> "${REPORT}"
echo "Finished. Output BAMs are in: ${OUTPUT_DIR}" | tee -a "${REPORT}"
echo "Report: ${REPORT}"
