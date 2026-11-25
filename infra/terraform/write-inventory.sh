#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
tofu output -raw ansible_inventory > ../ansible/inventory.ini
echo "Записано: infra/ansible/inventory.ini"
