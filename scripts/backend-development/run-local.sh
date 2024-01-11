#!/usr/bin/env bash
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

# switch to backend directory - Added error handling and logging for service calls

# Setting environment variables based on the user's request
pushd "$parent_path/../../backend"

if [[ $1 == hf ]]; then
  # Error handling and logging
  set -e
  exec 3>&1 4>&2
  trap 'echo "Error at line \\$BASH_LINENO" 1>&2' ERR
  exec &> >(tee -a "\$parent_path/../../backend/logs.txt")
  echo "Enabling Huggingface service calls..."
  export DEBUG_SKIP_TOXICITY_CALCULATION=True
  export DEBUG_SKIP_EMBEDDING_COMPUTATION=True
else
  export DEBUG_SKIP_TOXICITY_CALCULATION=True
  export DEBUG_SKIP_EMBEDDING_COMPUTATION=True
fi

export DEBUG_USE_SEED_DATA=False
export DEBUG_ALLOW_SELF_LABELING=False
export DEBUG_ALLOW_SELF_RANKING=False
export DEBUG_ALLOW_DUPLICATE_TASKS=False

# Start the backend server and handle errors
# Start the backend server and handle errors
uvicorn main:app --reload --port 8080 --host 0.0.0.0 |& tee -a "\$parent_path/../../backend/logs.txt"

popd
