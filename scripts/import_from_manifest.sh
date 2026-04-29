#!/bin/bash

# This script imports data from a manifest file into a Cavatica project.
# It assumes:
# the manifest has already been reviewed,
# the project exists,
# the import bucket is configured on Cavatica,
# you have the necessary permissions
# you have the AWS cli installed and configured,
# and you have a Cavatica profile configured.

# OPTIONS:
#   -a <aws_bucket_name>: The name of the AWS S3 bucket where the data are stored.
#   -c <cavatica_profile>: The name of the Cavatica profile to use for authentication.
#   -m <manifest_file>: The path to the manifest file with file_names to import.
#   -p <project_id>: The ID of the Cavatica project to import into (in form username/project_name).
#   -v <volume_name>: The name of the volume in Cavatica import from (in form username/volume_name).

set -euo pipefail
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )


# make options
while getopts "a:c:m:p:v:" opt; do
  case $opt in
    a) AWS_BUCKET_NAME=${OPTARG} ;;
    c) CAVATICA_PROFILE=${OPTARG} ;;
    m) MANIFEST_FILE=${OPTARG} ;;
    p) PROJECT_ID=${OPTARG} ;;
    v) VOLUME_NAME=${OPTARG} ;;
    *) echo "Usage: $0 -a <aws_bucket_name> -c <cavatica_profile> -m <manifest_file> -p <project_id> -v <volume_name>" >&2
       exit 1 ;;
  esac
done

if [[ -z "$AWS_BUCKET_NAME" || -z "$PROJECT_ID" || -z "$MANIFEST_FILE" || -z "$CAVATICA_PROFILE" || -z "$VOLUME_NAME" ]]; then
  echo "Usage: $0 -a <aws_bucket_name> -c <cavatica_profile> -m <manifest_file> -p <project_id> -v <volume_name>" >&2
  exit 1
fi

# make a file with the aws keys to import
aws s3api list-objects-v2 --output text --bucket $AWS_BUCKET_NAME --query 'Contents[].Key' | tr '\t' '\n' | grep "$(cut -f 6 ${MANIFEST_FILE})" | grep -v ".md5$" > keys_file.txt

# run the import script
python ${SCRIPT_DIR}/bulk_import.py --project $PROJECT_ID --volume $VOLUME_NAME --s3-keys-file keys_file.txt --profile $CAVATICA_PROFILE --run

# remove the keys_file
rm keys_file.txt