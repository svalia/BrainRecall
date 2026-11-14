#!/usr/bin/env bash
set -euo pipefail

SERVER="root@5.35.13.4"
SSH_KEY="$HOME/.ssh/owncome_deploy"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no"

echo "==> Syncing BrainRecall source to Selectel ($SERVER:/opt/brainrecall/app)..."
ssh $SSH_OPTS "$SERVER" "mkdir -p /opt/brainrecall/app /var/lib/brainrecall/files"

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '*.db' \
  --exclude '.env*' \
  --exclude 'TGandDSAPItokens.rtf' \
  --exclude 'BrainRecall-design*' \
  --exclude '*.zip' \
  -e "ssh $SSH_OPTS" \
  ./ "$SERVER:/opt/brainrecall/app/"

echo "==> Running remote setup & restarting brainrecall.service..."
ssh $SSH_OPTS "$SERVER" 'bash -s' << 'EOF'
set -euo pipefail

if ! id -u brainrecall >/dev/null 2>&1; then
  useradd --system --home-dir /opt/brainrecall --shell /usr/sbin/nologin brainrecall
fi

chown -R brainrecall:brainrecall /opt/brainrecall /var/lib/brainrecall

if [ ! -d /opt/brainrecall/venv ]; then
  python3 -m venv /opt/brainrecall/venv
fi

/opt/brainrecall/venv/bin/pip install --quiet --upgrade pip
/opt/brainrecall/venv/bin/pip install --quiet -e "/opt/brainrecall/app[dev]"

cp /opt/brainrecall/app/deploy/brainrecall.service /etc/systemd/system/brainrecall.service
systemctl daemon-reload
systemctl enable brainrecall.service
systemctl restart brainrecall.service

for i in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8096/health >/dev/null 2>&1; then
    echo "BrainRecall local health check passed!"
    curl -sS http://127.0.0.1:8096/health
    echo ""
    break
  fi
  sleep 1
done
EOF
