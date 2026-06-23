#!/usr/bin/env bash
# =============================================================
# report-collection-portal 一键部署脚本
# 适用：Ubuntu 22.04 / 24.04
# 用法：sudo bash setup.sh
# =============================================================
set -euo pipefail

# ── 可修改变量 ────────────────────────────────────────────────
APP_USER="root"                            # 运行服务的系统用户
APP_DIR="/var/www/html/report-collection-portal"  # 部署目录
DOMAIN=""                                  # 域名（留空则用 IP 访问）
DB_NAME="report_portal"
DB_USER="portal"
DB_PASS="$(openssl rand -hex 16)"         # 自动生成强密码，也可手动指定
SECRET_KEY="$(openssl rand -hex 32)"
PYTHON_VERSION="3.11"

# ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

[[ $EUID -ne 0 ]] && { echo "请用 sudo 运行此脚本"; exit 1; }

# ── 1. 系统更新 ───────────────────────────────────────────────
info "1/9  更新系统包..."
apt-get update -qq
apt-get install -y -qq software-properties-common

# 若默认源没有 Python 3.11，添加 deadsnakes PPA
if ! apt-cache show python${PYTHON_VERSION} &>/dev/null; then
  info "   添加 deadsnakes PPA 以安装 Python ${PYTHON_VERSION}..."
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -qq
fi

apt-get install -y -qq \
  curl wget git build-essential \
  python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev \
  libpq-dev unixodbc-dev \
  nginx certbot python3-certbot-nginx \
  postgresql postgresql-contrib

# ── 2. Node.js 20（通过 nvm，不影响系统全局 node） ───────────
info "2/9  安装 Node.js 20 via nvm..."
export NVM_DIR="/root/.nvm"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi
source "$NVM_DIR/nvm.sh"
nvm install 20 --no-progress
nvm use 20
NODE_BIN="$(nvm which 20)"
NPM_BIN="$(dirname "$NODE_BIN")/npm"
info "   使用 Node: $NODE_BIN ($(node --version))"

# ── 3. Microsoft ODBC Driver 17（SQL Server 同步功能） ───────
info "3/9  安装 ODBC Driver 17 for SQL Server..."
if ! dpkg -l msodbcsql17 &>/dev/null; then
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
    https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/mssql-release.list
  apt-get update -qq
  ACCEPT_EULA=Y apt-get install -y -qq msodbcsql17 unixodbc-dev
fi

# ── 4. PostgreSQL 数据库 ──────────────────────────────────────
info "4/9  配置 PostgreSQL..."
systemctl enable --now postgresql

# 创建数据库用户和库（幂等）
sudo -u postgres psql -tc \
  "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c \
  "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tc \
  "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c \
  "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

info "   数据库密码（请保存）: ${DB_PASS}"

# ── 5. 确保目录存在 ──────────────────────────────────────────
info "5/9  确认目录结构..."
mkdir -p "${APP_DIR}/storage"

# ── 6. 确认项目目录 ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info "6/9  项目已在 ${APP_DIR}，跳过拷贝..."

# ── 7. 后端 Python 环境 ───────────────────────────────────────
info "7/9  安装后端依赖..."
VENV="${APP_DIR}/backend/.venv"
if [[ ! -d "${VENV}" ]]; then
  python${PYTHON_VERSION} -m venv "${VENV}"
fi
"${VENV}/bin/pip" install -q --upgrade pip
"${VENV}/bin/pip" install -q -r "${APP_DIR}/backend/requirements.txt"

# 生成 .env（仅在不存在时创建）
ENV_FILE="${APP_DIR}/backend/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
APP_NAME=Report Collection Portal API
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
STORAGE_DIR=${APP_DIR}/storage
ALLOWED_ORIGINS=http://localhost,http://127.0.0.1${DOMAIN:+,https://${DOMAIN},http://${DOMAIN}}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=480

SQLSERVER_HOST=
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=
SQLSERVER_USER=
SQLSERVER_PASSWORD=
SQLSERVER_ODBC_DRIVER=ODBC Driver 17 for SQL Server
SQLSERVER_ENCRYPT=yes
SQLSERVER_TRUST_SERVER_CERTIFICATE=yes

TEAMS_WEBHOOK_URL=
ONEDRIVE_ENABLED=false
ONEDRIVE_TENANT_ID=
ONEDRIVE_CLIENT_ID=
ONEDRIVE_CLIENT_SECRET=
ONEDRIVE_SITE_ID=
ONEDRIVE_DRIVE_ID=
ONEDRIVE_ROOT_FOLDER=报表原始文件
KEEP_LOCAL_COPY=true

PADDLE_OCR_CACHE_DIR=${APP_DIR}/storage/.ocr_cache
EOF
  chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
  chmod 640 "${ENV_FILE}"
  warn "   .env 已生成：${ENV_FILE}，请按需补充 SQLSERVER / TEAMS 等配置"
fi

# ── 8. 前端构建 ──────────────────────────────────────────────
info "8/9  构建前端（Node $(node --version)）..."
cd "${APP_DIR}/frontend"
"$NPM_BIN" ci --silent
"$NPM_BIN" run build

# ── 9. systemd 服务 + Apache 配置 ───────────────────────────
info "9/9  配置 systemd 服务..."
cp "${SCRIPT_DIR}/portal-backend.service" /etc/systemd/system/
sed -i \
  -e "s|__APP_DIR__|${APP_DIR}|g" \
  /etc/systemd/system/portal-backend.service

systemctl daemon-reload
systemctl enable --now portal-backend

# ── Apache 反向代理 ───────────────────────────────────────────
info "配置 Apache..."
a2enmod proxy proxy_http rewrite
cp "${SCRIPT_DIR}/apache-portal.conf" /etc/apache2/conf-available/portal.conf
sed -i "s|__APP_DIR__|${APP_DIR}|g" /etc/apache2/conf-available/portal.conf
a2enconf portal
systemctl reload apache2

# ── 完成 ─────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "  访问地址：http://${DOMAIN:-${SERVER_IP}}"
echo "  后端日志：journalctl -u portal-backend -f"
echo "  重启后端：systemctl restart portal-backend"
echo "  DB 密码已写入 ${ENV_FILE}"
echo ""
echo "  后续步骤："
echo "  1. 编辑 ${ENV_FILE} 填写 SQLSERVER / TEAMS 等配置"
echo "  2. 打开浏览器访问，进入「指标管理 → 系统」初始化数据库"
echo "=========================================="
