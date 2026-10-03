#!/usr/bin/env bash
# DEPRECATED — deploy logic moved to scripts/deploy.sh (ops lane).
# Kept so old muscle memory (`./deploy-aws.sh` from server/) still works.
# New features there: auto NLB target re-registration, local-or-CodeBuild
# build switch, task def with secrets/dashboard env, loud failure paths.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/../scripts/deploy.sh" "$@"
