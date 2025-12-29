#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------
# 🔧 Configuration
# --------------------------------------
VAULT="kubernetes"                          # Nom du coffre 1Password (adapter si besoin)
ITEM_NAME="talos"                        # Nom de l'item (ce que Just recherche)
SECRETS_FILE="${1:-./secrets.env}"  # Fichier source des secrets Talos

# --------------------------------------
# 🧩 Vérifications
# --------------------------------------
command -v op >/dev/null || { echo "❌ op CLI not found"; exit 1; }
command -v yq >/dev/null || { echo "❌ yq not found"; exit 1; }

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "❌ Secrets file not found: $SECRETS_FILE"
  exit 1
fi

echo "🔐 Importing Talos secrets into 1Password vault: $VAULT"
echo "📄 Source: $SECRETS_FILE"
echo

# --------------------------------------
# 🔎 Extraction des champs dans secrets.yaml
# --------------------------------------
MACHINE_CA_CRT=$(yq -r '.certs.os.crt' "$SECRETS_FILE")
MACHINE_CA_KEY=$(yq -r '.certs.os.key' "$SECRETS_FILE")
MACHINE_TOKEN=$(yq -r '.trustdinfo.token' "$SECRETS_FILE")

CLUSTER_CA_CRT=$(yq -r '.certs.k8s.crt' "$SECRETS_FILE")
CLUSTER_CA_KEY=$(yq -r '.certs.k8s.key' "$SECRETS_FILE")
CLUSTER_AGGREGATORCA_CRT=$(yq -r '.certs.k8saggregator.crt' "$SECRETS_FILE")
CLUSTER_AGGREGATORCA_KEY=$(yq -r '.certs.k8saggregator.key' "$SECRETS_FILE")
CLUSTER_ETCD_CA_CRT=$(yq -r '.certs.etcd.crt' "$SECRETS_FILE")
CLUSTER_ETCD_CA_KEY=$(yq -r '.certs.etcd.key' "$SECRETS_FILE")
CLUSTER_SERVICEACCOUNT_KEY=$(yq -r '.certs.k8sserviceaccount.key' "$SECRETS_FILE")

CLUSTER_ID=$(yq -r '.cluster.id' "$SECRETS_FILE")
CLUSTER_SECRET=$(yq -r '.cluster.secret' "$SECRETS_FILE")
CLUSTER_TOKEN=$(yq -r '.secrets.bootstraptoken' "$SECRETS_FILE")
CLUSTER_SECRETBOXENCRYPTIONSECRET=$(yq -r '.secrets.secretboxencryptionsecret' "$SECRETS_FILE")

# --------------------------------------
# 🧠 Vérification basique
# --------------------------------------
for var in \
  MACHINE_CA_CRT MACHINE_CA_KEY CLUSTER_CA_CRT CLUSTER_CA_KEY \
  CLUSTER_ID CLUSTER_SECRET CLUSTER_TOKEN CLUSTER_SECRETBOXENCRYPTIONSECRET; do
  if [[ -z "${!var}" || "${!var}" == "null" ]]; then
    echo "⚠️  Missing or null value for $var"
  fi
done

# --------------------------------------
# 🏗️ Création du coffre s'il n'existe pas
# --------------------------------------
if ! op vault get "$VAULT" >/dev/null 2>&1; then
  echo "🆕 Creating vault '$VAULT'..."
  op vault create "$VAULT"
else
  echo "✅ Vault '$VAULT' exists."
fi

# --------------------------------------
# 🧱 Création / mise à jour de l'item "talos"
# --------------------------------------
if op item get "$ITEM_NAME" --vault "$VAULT" >/dev/null 2>&1; then
  echo "↪️  Updating existing item '$ITEM_NAME'..."
  op item edit "$ITEM_NAME" --vault "$VAULT" \
    "MACHINE_CA_CRT=$MACHINE_CA_CRT" \
    "MACHINE_CA_KEY=$MACHINE_CA_KEY" \
    "MACHINE_TOKEN=$MACHINE_TOKEN" \
    "CLUSTER_CA_CRT=$CLUSTER_CA_CRT" \
    "CLUSTER_CA_KEY=$CLUSTER_CA_KEY" \
    "CLUSTER_AGGREGATORCA_CRT=$CLUSTER_AGGREGATORCA_CRT" \
    "CLUSTER_AGGREGATORCA_KEY=$CLUSTER_AGGREGATORCA_KEY" \
    "CLUSTER_ETCD_CA_CRT=$CLUSTER_ETCD_CA_CRT" \
    "CLUSTER_ETCD_CA_KEY=$CLUSTER_ETCD_CA_KEY" \
    "CLUSTER_SERVICEACCOUNT_KEY=$CLUSTER_SERVICEACCOUNT_KEY" \
    "CLUSTER_ID=$CLUSTER_ID" \
    "CLUSTER_SECRET=$CLUSTER_SECRET" \
    "CLUSTER_TOKEN=$CLUSTER_TOKEN" \
    "CLUSTER_SECRETBOXENCRYPTIONSECRET=$CLUSTER_SECRETBOXENCRYPTIONSECRET"
else
  echo "🆕 Creating new item '$ITEM_NAME'..."
  op item create \
    --vault "$VAULT" \
    --category "Secure Note" \
    --title "$ITEM_NAME" \
    "MACHINE_CA_CRT=$MACHINE_CA_CRT" \
    "MACHINE_CA_KEY=$MACHINE_CA_KEY" \
    "MACHINE_TOKEN=$MACHINE_TOKEN" \
    "CLUSTER_CA_CRT=$CLUSTER_CA_CRT" \
    "CLUSTER_CA_KEY=$CLUSTER_CA_KEY" \
    "CLUSTER_AGGREGATORCA_CRT=$CLUSTER_AGGREGATORCA_CRT" \
    "CLUSTER_AGGREGATORCA_KEY=$CLUSTER_AGGREGATORCA_KEY" \
    "CLUSTER_ETCD_CA_CRT=$CLUSTER_ETCD_CA_CRT" \
    "CLUSTER_ETCD_CA_KEY=$CLUSTER_ETCD_CA_KEY" \
    "CLUSTER_SERVICEACCOUNT_KEY=$CLUSTER_SERVICEACCOUNT_KEY" \
    "CLUSTER_ID=$CLUSTER_ID" \
    "CLUSTER_SECRET=$CLUSTER_SECRET" \
    "CLUSTER_TOKEN=$CLUSTER_TOKEN" \
    "CLUSTER_SECRETBOXENCRYPTIONSECRET=$CLUSTER_SECRETBOXENCRYPTIONSECRET"
fi

echo
echo "🎉 All Talos secrets imported successfully."
echo "🔎 Test example:"
echo "    op read op://$VAULT/$ITEM_NAME/CLUSTER_ID"