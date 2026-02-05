#!/usr/bin/env bash
set -euo pipefail

# 変数定義（お好みで変更可）
resourceGroup="rg-ms-foundry-mcp"
location="canadaeast"          # 任意のリージョン（例：カナダ東部）
storageNameBase="stmcpserver"  # ストレージ アカウント名のベース（小文字英数字のみ）
functionNameBase="func-mcp-server" # Function App 名のベース

# グローバルで一意になるようにランダムサフィックスを付与（000000〜999999）
randomSuffix=$(printf "%06d" $((RANDOM % 1000000)))

storageName="${storageNameBase}${randomSuffix}"
functionName="${functionNameBase}-${randomSuffix}"

echo "Using resource group : ${resourceGroup}"
echo "Using location       : ${location}"
echo "Using storage name   : ${storageName}"
echo "Using function name  : ${functionName}"

# リソース グループ作成（1 回だけ）
az group create \
  --name "${resourceGroup}" \
  --location "${location}"

# Function App 用ストレージ アカウント作成（1 回だけ）
az storage account create \
  --name "${storageName}" \
  --resource-group "${resourceGroup}" \
  --location "${location}" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --tags SecurityControl=Ignore \
  --allow-shared-key-access true \
  --output none

# （任意）Blob コンテナー作成
az storage container create \
  --name "mcp-data" \
  --account-name "${storageName}" \
  --auth-mode login

# 接続文字列取得
storageConn=$(az storage account show-connection-string \
  --resource-group "${resourceGroup}" \
  --name "${storageName}" \
  --query connectionString -o tsv)

# ==============================
# Flex Consumption Function App 作成
# ==============================
az functionapp create \
  --resource-group "${resourceGroup}" \
  --name "${functionName}" \
  --storage-account "${storageName}" \
  --flexconsumption-location "${location}" \
  --runtime python \
  --runtime-version 3.12

# ==============================
# アプリ設定
# ==============================
az functionapp config appsettings set \
  --resource-group "${resourceGroup}" \
  --name "${functionName}" \
  --settings \
    AzureWebJobsStorage="${storageConn}" \
    DEPLOYMENT_STORAGE_CONNECTION_STRING="${storageConn}" \
    AzureWebJobsFeatureFlags="EnableMcpCustomHandlerPreview" \
    PYTHONPATH="/home/site/wwwroot/.python_packages/lib/site-packages"
    # FUNCTIONS_EXTENSION_VERSION="~4" \
    # FUNCTIONS_WORKER_RUNTIME="python"

# Azure Functions Core Tools を使ってデプロイ
func azure functionapp publish "${functionName}" --python