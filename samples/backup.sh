#!/bin/bash
if [ -z ${BASH_SOURCE+x} ]; then SCRIPT_FILEPATH=${(%):-%N};
else SCRIPT_FILEPATH=${BASH_SOURCE[0]}; fi
SCRIPT_FILEPATH=$( realpath -P ${SCRIPT_FILEPATH} )
SCRIPT_DIRPATH=$( dirname "${SCRIPT_FILEPATH}" )
PYTHON_BIN_PATH="$(python3 -m site --user-base)/bin"

${PYTHON_BIN_PATH}/backup_cli \
  --config ${SCRIPT_DIRPATH}/backup_config.yaml \
  $@