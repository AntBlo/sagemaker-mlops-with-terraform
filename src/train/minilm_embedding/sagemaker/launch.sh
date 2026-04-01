#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

fix_local_mode_permissions() {
	local owner uid gid path

	owner="/opt/ml/input/data/code"
	uid="$(stat -c '%u' "$owner" 2>/dev/null || echo 0)"
	gid="$(stat -c '%g' "$owner" 2>/dev/null || echo 0)"

	for path in /opt/ml/input /opt/ml/output /opt/ml/model; do
		[[ -e "$path" ]] || continue
		chown -R "$uid:$gid" "$path" 2>/dev/null || true
		chmod -R u+rwX,go+rwX "$path" 2>/dev/null || true
	done
}

trap fix_local_mode_permissions EXIT


python --version | awk '{print $2}' > .python-version

pip freeze > pre-installed-requirements.txt

pip install -r requirements.txt

python train.py "$@"

trap fix_local_mode_permissions EXIT
