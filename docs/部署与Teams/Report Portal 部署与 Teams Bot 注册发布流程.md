# Report Portal 部署与 Teams Bot 注册发布流程

生成日期：2026-06-23  
项目：Report Portal / Report Collection Portal  
当前公网域名：`https://julongtongchuan.icu`  
当前 GitHub 仓库：`https://github.com/ChrisYou666/report-portal.git`

## 1. 当前状态

当前已经完成：

- 代码已推送到 GitHub 仓库：`ChrisYou666/report-portal`
- 阿里云服务器已部署后端、前端、PostgreSQL、Nginx 反向代理
- 后端健康检查已通过：`https://julongtongchuan.icu/report-portal/api/health`
- 前端页面已可访问：`https://julongtongchuan.icu/report-portal/indicator`
- Teams Bot 已创建：`Report Portal Bot`
- Teams Bot endpoint 已配置：`https://julongtongchuan.icu/report-portal/api/teams-bot/messages`
- Teams App validation 已通过
- Teams 管理中心里 App 已从 `Blocked` 改为 `Unblocked`
- App 可用范围已设置为：`Everyone`

当前还需要继续做：

- 管理员把 App 自动安装给用户，或让用户手动安装
- 把 Bot 加入需要接收通知的个人聊天、群聊或频道
- 在系统里给每个指标配置 Teams 通知目标和发送时间

## 2. 部署目标路径

公网访问路径：

```text
前端页面：
https://julongtongchuan.icu/report-portal/indicator

后端 API：
https://julongtongchuan.icu/report-portal/api/

健康检查：
https://julongtongchuan.icu/report-portal/api/health

Teams Bot endpoint：
https://julongtongchuan.icu/report-portal/api/teams-bot/messages
```

服务器路径：

```text
项目目录：
/opt/report-portal

后端目录：
/opt/report-portal/backend

前端静态文件目录：
/var/www/report-portal

后端 systemd 服务：
report-portal-backend.service

后端监听地址：
127.0.0.1:18000

PostgreSQL 容器：
report-portal-postgres

PostgreSQL 端口：
127.0.0.1:15432
```

## 3. 服务器部署流程

### 3.1 拉取代码

```bash
cd /opt
git clone https://github.com/ChrisYou666/report-portal.git report-portal
cd /opt/report-portal
```

如果已经部署过，更新代码：

```bash
cd /opt/report-portal
git pull
```

### 3.2 启动 PostgreSQL

项目根目录已有 `docker-compose.yml`，PostgreSQL 使用 Docker 启动：

```bash
cd /opt/report-portal
docker compose up -d postgres
docker ps | grep report-portal-postgres
```

注意：数据库密码不要写进交接文档明文，只写到服务器 `.env` 或服务器安全凭据里。

### 3.3 配置后端 `.env`

编辑：

```bash
nano /opt/report-portal/backend/.env
```

关键配置示例：

```env
DATABASE_URL=postgresql+psycopg://portal:<数据库密码>@127.0.0.1:15432/report_portal
STORAGE_DIR=storage
ALLOWED_ORIGINS=https://julongtongchuan.icu

TEAMS_PORTAL_URL=https://julongtongchuan.icu/report-portal/indicator
TEAMS_BOT_APP_ID=72ba3fa0-13ee-4386-9606-3c5a011a41e8
TEAMS_BOT_TENANT_ID=49306cd1-4f6e-45ae-9eff-59a1bd8936d2
TEAMS_BOT_APP_PASSWORD=<Azure 新建客户端密码后复制的 Client secret value>
TEAMS_BOT_VALIDATE_INCOMING=true
TEAMS_BOT_NAME=Report Portal Bot
```

重点：

- `TEAMS_BOT_APP_PASSWORD` 必须填 `Client secret value`
- 不要填 `Secret ID`
- Client secret value 只在创建时显示一次，丢失后只能重新创建
- `.env` 不要提交到 GitHub

### 3.4 安装后端依赖

```bash
cd /opt/report-portal/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.5 创建后端 systemd 服务

创建：

```bash
nano /etc/systemd/system/report-portal-backend.service
```

内容：

```ini
[Unit]
Description=Report Portal Backend
After=network.target docker.service

[Service]
WorkingDirectory=/opt/report-portal/backend
EnvironmentFile=/opt/report-portal/backend/.env
ExecStart=/opt/report-portal/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
systemctl daemon-reload
systemctl enable --now report-portal-backend
systemctl status report-portal-backend --no-pager -l
```

### 3.6 构建前端

```bash
cd /opt/report-portal/frontend
npm ci
npm run build
rm -rf /var/www/report-portal
mkdir -p /var/www/report-portal
cp -r dist/* /var/www/report-portal/
```

### 3.7 配置 Nginx

将 Report Portal 放在现有域名的 `/report-portal/` 下，避免影响同传已有服务。

Nginx 里需要包含这些 location：

```nginx
location = /report-portal {
    return 301 /report-portal/;
}

location /report-portal/assets/ {
    root /var/www;
    add_header Cache-Control "public, max-age=31536000, immutable";
    try_files $uri =404;
}

location /report-portal/api/ {
    proxy_pass http://127.0.0.1:18000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /report-portal/storage/ {
    proxy_pass http://127.0.0.1:18000/storage/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /report-portal/ {
    root /var/www;
    add_header Cache-Control "no-cache";
    try_files $uri $uri/ /report-portal/indicator.html;
}
```

检查并重载：

```bash
nginx -t
systemctl reload nginx
```

### 3.8 部署验证

后端本机验证：

```bash
curl -s http://127.0.0.1:18000/api/health
```

公网后端验证：

```bash
curl -s https://julongtongchuan.icu/report-portal/api/health
```

正确返回：

```json
{"status":"ok"}
```

前端验证：

```bash
curl -I https://julongtongchuan.icu/report-portal/indicator
```

正确结果应包含：

```text
HTTP/1.1 200 OK
```

Bot endpoint 验证：

```bash
curl -I https://julongtongchuan.icu/report-portal/api/teams-bot/messages
```

正常会返回：

```text
405 Method Not Allowed
allow: POST
```

说明：`/teams-bot/messages` 只接受 Teams 发来的 `POST`，用浏览器或 `curl -I` 测到 `405` 是正常的。

## 4. Teams Bot 注册流程

### 4.1 创建 Bot

进入 Teams Developer Portal：

```text
https://dev.teams.microsoft.com/
```

路径：

```text
Tools → Bots → New Bot
```

Bot 名称：

```text
Report Portal Bot
```

当前 Bot 信息：

```text
Bot / Microsoft App ID：
72ba3fa0-13ee-4386-9606-3c5a011a41e8

Tenant ID：
49306cd1-4f6e-45ae-9eff-59a1bd8936d2

Bot endpoint：
https://julongtongchuan.icu/report-portal/api/teams-bot/messages
```

### 4.2 配置 Bot endpoint

Teams Developer Portal：

```text
Tools → Bots → Report Portal Bot → Configure
```

填写：

```text
Endpoint address:
https://julongtongchuan.icu/report-portal/api/teams-bot/messages
```

保存。

### 4.3 创建 Client Secret

进入 Azure App Registration 凭据页面：

```text
https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Credentials/appId/72ba3fa0-13ee-4386-9606-3c5a011a41e8
```

操作：

```text
Certificates & secrets → New client secret
```

创建后复制：

```text
Value
```

不要复制：

```text
Secret ID
```

将 `Value` 写入服务器：

```bash
nano /opt/report-portal/backend/.env
```

更新：

```env
TEAMS_BOT_APP_PASSWORD=<Client secret value>
```

重启后端：

```bash
systemctl restart report-portal-backend
```

验证 Bot 是否能主动发消息：

```bash
cd /opt/report-portal/backend
. .venv/bin/activate

python3 <<'PY'
from app.db import SessionLocal
from app.models import TeamsBotConversation
from app.services.teams_bot import send_text_message

db = SessionLocal()
target = db.query(TeamsBotConversation).order_by(TeamsBotConversation.last_seen_at.desc()).first()
print(send_text_message(target, "Manual test from Report Portal Bot"))
PY
```

如果 Teams 里收到 `Manual test from Report Portal Bot`，说明 Bot 主动推送链路正常。

## 5. Teams App Manifest

当前可用的 `manifest.json`：

```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.25/MicrosoftTeams.schema.json",
  "version": "1.0.1",
  "manifestVersion": "1.25",
  "id": "8c5d2df2-4650-4d73-be4c-d17e28b26e5d",
  "name": {
    "short": "Report Portal Bot"
  },
  "developer": {
    "name": "Julong",
    "websiteUrl": "https://julongtongchuan.icu",
    "privacyUrl": "https://julongtongchuan.icu",
    "termsOfUseUrl": "https://julongtongchuan.icu"
  },
  "description": {
    "short": "Report portal notification bot",
    "full": "Sends scheduled report portal indicator notifications to Teams."
  },
  "icons": {
    "outline": "outline.png",
    "color": "color.png"
  },
  "accentColor": "#FFFFFF",
  "bots": [
    {
      "botId": "72ba3fa0-13ee-4386-9606-3c5a011a41e8",
      "scopes": [
        "personal",
        "team",
        "groupChat"
      ],
      "isNotificationOnly": false,
      "supportsCalling": false,
      "supportsVideo": false,
      "supportsFiles": false
    }
  ],
  "validDomains": [
    "julongtongchuan.icu"
  ],
  "supportsChannelFeatures": "tier1"
}
```

注意：

- 当前不使用 Teams SSO，所以不要加 `webApplicationInfo`
- 如果加了 `webApplicationInfo` 但没有 `resource`，验证会出现警告
- 如果 manifest version 是 `1.25` 且支持 `team` scope，需要保留 `supportsChannelFeatures`
- 每次重新上传或发布时，如果 Teams 缓存旧包，可以把 `version` 从 `1.0.1` 升到 `1.0.2`

## 6. Teams App 验证和发布

Teams Developer Portal：

```text
Apps → Report Portal Bot → Publish → App validation
```

验证通过后：

```text
Publish → Publish to your org
```

发布给组织后，需要 Teams 管理员审批和放行。

## 7. Teams 管理员审批和放行

Teams 管理中心：

```text
https://admin.teams.microsoft.com/policies/manage-apps
```

路径：

```text
Teams apps → Manage apps
```

搜索：

```text
Report Portal Bot
```

进入后将状态改为：

```text
Unblocked / Allowed
```

当前已完成：

```text
App status: Unblocked
Available to: Everyone
```

### 7.1 自动安装给所有用户

方式一：在 `Manage apps` 页面直接安装：

```text
勾选 Report Portal Bot → Edit installs → 选择 Everyone / Entire org / All users → Save
```

方式二：使用 Setup policy：

```text
https://admin.teams.microsoft.com/policies/app-setup
```

路径：

```text
Teams apps → Setup policies → Global (Org-wide default) → Installed apps → Add apps → Report Portal Bot → Save
```

说明：

- 自动安装通常是安装到用户个人 Teams 应用里
- 频道通知仍然需要把 Bot 加入具体 Team 或频道
- 策略生效不是实时的，可能需要等待几分钟到几小时

## 8. 安装 Bot 并捕获通知目标

### 8.1 个人聊天

Teams 客户端：

```text
Apps → 搜索 Report Portal Bot → Add
```

安装后给 Bot 发：

```text
Hi
```

Bot 应回复：

```text
Hi, Report Portal Bot is running. Open portal: https://julongtongchuan.icu/report-portal/indicator
```

### 8.2 频道

进入目标 Team / Channel：

```text
频道右上角 ... → Apps / Manage channel → 添加 Report Portal Bot
```

然后在频道里发送：

```text
@Report Portal Bot Hi
```

系统收到 Teams 请求后，会把该频道或聊天保存到数据库表：

```text
teams_bot_conversations
```

### 8.3 查看服务器日志

```bash
journalctl -u report-portal-backend -n 150 --no-pager
```

正常应该看到：

```text
POST /api/teams-bot/messages HTTP/1.1" 200 OK
```

## 9. 在系统里配置指标通知

打开系统：

```text
https://julongtongchuan.icu/report-portal/indicator
```

进入：

```text
配置管理 → 通知配置 → 指标 Bot 定时通知
```

操作：

```text
1. 点击 刷新目标
2. 给每个指标选择 Teams 目标
3. 设置发送小时和分钟
4. 启用
5. 保存
6. 点击测试发送
```

链接规则：

```text
综合指数：
https://julongtongchuan.icu/report-portal/indicator?index=composite

农业：
https://julongtongchuan.icu/report-portal/indicator?index=agri

期货：
https://julongtongchuan.icu/report-portal/indicator?index=futures
```

Teams 消息里会带对应指标链接，点击后打开系统前端，并优先选中对应指标。

## 10. 常见问题

### 10.1 `curl -I /teams-bot/messages` 返回 405

这是正常的。

```text
405 Method Not Allowed
allow: POST
```

Teams Bot endpoint 只接受 `POST`。

### 10.2 Teams 发了 `Hi`，Bot 没回复

先看日志：

```bash
journalctl -u report-portal-backend -n 150 --no-pager
```

如果日志里没有：

```text
POST /api/teams-bot/messages
```

说明 Teams 没有打到服务器，要检查 endpoint、App 安装版本、管理员是否放行。

如果日志里有 `400 Bad Request`，手动测主动发送：

```bash
cd /opt/report-portal/backend
. .venv/bin/activate

python3 <<'PY'
from app.db import SessionLocal
from app.models import TeamsBotConversation
from app.services.teams_bot import send_text_message

db = SessionLocal()
target = db.query(TeamsBotConversation).order_by(TeamsBotConversation.last_seen_at.desc()).first()
try:
    print(send_text_message(target, "Manual test from Report Portal Bot"))
except Exception as e:
    print(repr(e))
PY
```

如果出现：

```text
invalid_client
Invalid client secret provided
```

说明 `TEAMS_BOT_APP_PASSWORD` 填错了，需要重新创建 Client secret，并填 `Value`。

### 10.3 App validation 失败：`Unable to upload the manifest.zip file in MS Teams`

处理顺序：

```text
1. manifest 的 version 加 1，例如 1.0.1 改成 1.0.2
2. 重新保存 manifest
3. 重新 App validation
4. 如果仍失败，检查 Teams 管理中心是否禁止上传或安装自定义 App
```

### 10.4 Teams 管理中心显示 `Blocked`

处理：

```text
Teams admin center → Teams apps → Manage apps → Report Portal Bot → Allow / Unblock
```

还需要确认：

```text
Available to: Everyone
```

### 10.5 安装给所有人后还是看不到

可能原因：

- Teams 策略生效有延迟
- 用户 Teams 客户端缓存未刷新
- 只设置了 `Available to Everyone`，但没有设置 `Edit installs` 或 Setup policy
- 用户所在策略不是 `Global (Org-wide default)`

## 11. 后续更新部署

更新后端代码：

```bash
cd /opt/report-portal
git pull
systemctl restart report-portal-backend
curl -s https://julongtongchuan.icu/report-portal/api/health
```

如果前端也有修改：

```bash
cd /opt/report-portal/frontend
npm ci
npm run build
rm -rf /var/www/report-portal
mkdir -p /var/www/report-portal
cp -r dist/* /var/www/report-portal/
systemctl reload nginx
```

## 12. 安全注意事项

- 不要把服务器密码写进文档
- 不要把 `.env` 提交到 GitHub
- 不要在聊天或文档里明文保存 `TEAMS_BOT_APP_PASSWORD`
- 如果 Client secret 已泄露，立刻在 Azure 删除旧 secret 并新建
- 文档里只保留 App ID、Tenant ID、endpoint、域名等非密钥信息

## 13. 官方参考

- Teams Developer Portal 管理 App：`https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/manage-your-apps-in-developer-portal`
- Teams 管理中心允许或阻止 App：`https://learn.microsoft.com/en-us/microsoftteams/manage-apps`
- Teams App setup policies：`https://learn.microsoft.com/en-us/microsoftteams/teams-app-setup-policies`
- Teams custom app policies：`https://learn.microsoft.com/en-us/microsoftteams/teams-custom-app-policies-and-settings`
