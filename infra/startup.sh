#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/startup-script.log) 2>&1
set -x

# Install Docker
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: bookworm
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
apt-get install -y git python3.11-venv

# Clone repo
git clone https://github.com/bhawkyard1/thames_tide_times.git /app
cd /app

# Python data prep
python3 -m venv venv
source venv/bin/activate
pip install pydantic
python3 data/sanitize_thames_path.py
deactivate

# Fetch secrets from Secret Manager
# (gcloud is pre-installed on Debian GCP images)
gcloud secrets versions access latest --secret=postgres_pwd    > /app/postgres_pwd
gcloud secrets versions access latest --secret=tidal_api_key   > /app/tidal_api_key
mkdir -p /app/nginx/certs
gcloud secrets versions access latest --secret=fullchain_pem   > /app/nginx/certs/fullchain.pem
gcloud secrets versions access latest --secret=privkey_pem     > /app/nginx/certs/privkey.pem

# Lock down secret files
chmod 600 /app/postgres_pwd /app/tidal_api_key /app/nginx/certs/*.pem

# Start app
docker compose -f /app/compose.yaml up -d --build