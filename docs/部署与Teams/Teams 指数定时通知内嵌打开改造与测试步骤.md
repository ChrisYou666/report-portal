# Teams 指数定时通知内嵌打开改造与测试步骤

生成日期：2026-06-23

## 目标

要实现的效果是：

1. 每个指数都可以单独配置定时发送到 Teams 个人、群聊或频道。
2. Teams 消息里带一个按钮或链接。
3. 点开后先看到对应指数，不是默认综合指数。
4. 尽量在 Teams 内部打开系统页面，而不是跳到外部浏览器。

## 这次代码要改什么

### 1. 后端通知链接改成 Teams App 深链接

原来发的是普通网页链接：

```text
https://julongtongchuan.icu/report-portal/indicator?index=agri
```

这种链接在 Teams 里经常会被浏览器打开。

现在改成 Teams 深链接：

```text
https://teams.microsoft.com/l/entity/{TeamsAppManifestId}/indicator?webUrl=...&label=...&context={"subEntityId":"agri"}
```

其中：

```text
TeamsAppManifestId = 8c5d2df2-4650-4d73-be4c-d17e28b26e5d
entityId = indicator
subEntityId = 指数代码，例如 agri、futures、industry
```

### 2. Teams 消息用按钮打开链接

通知卡片里使用 `Action.OpenUrl` 按钮，不再把链接直接写成一大段文本。

这样 Teams 更容易按 App 深链接处理，在 Teams 内打开对应 Tab。

### 3. 前端识别 Teams 传进来的指数代码

前端现在支持两种入口：

```text
普通网页：
https://julongtongchuan.icu/report-portal/indicator?index=agri

Teams App 深链接：
context.subEntityId = agri
```

所以点开“农业”通知时，会自动选中“农业”；点开“期货”通知时，会自动选中“期货”。

## 服务器 .env 需要有这些配置

文件：

```bash
/opt/report-portal/backend/.env
```

确认有：

```env
TEAMS_PORTAL_URL=https://julongtongchuan.icu/report-portal/indicator
TEAMS_APP_ID=8c5d2df2-4650-4d73-be4c-d17e28b26e5d
TEAMS_TAB_ENTITY_ID=indicator
TEAMS_DEEP_LINK_ENABLED=true
```

注意：

`TEAMS_APP_ID` 这里填的是 Teams App manifest 里的 `id`，不是 Bot ID。

Bot ID 是：

```text
72ba3fa0-13ee-4386-9606-3c5a011a41e8
```

## Teams Developer Portal 需要更新什么

你现在的 App 必须加一个 Tab，否则 Teams 深链接没有地方打开页面。

在 Developer Portal 的 manifest 里加入：

```json
"staticTabs": [
  {
    "entityId": "indicator",
    "name": "指数看板",
    "contentUrl": "https://julongtongchuan.icu/report-portal/indicator",
    "websiteUrl": "https://julongtongchuan.icu/report-portal/indicator",
    "scopes": [
      "personal",
      "team",
      "groupChat"
    ]
  }
]
```

同时保留：

```json
"validDomains": [
  "julongtongchuan.icu"
],
"supportsChannelFeatures": "tier1"
```

不要加回 `webApplicationInfo`，否则可能再次出现 SSO 相关警告。

已经生成好的完整 manifest 文件：

```text
C:\Users\22659\Documents\Codex\2026-06-22\du\outputs\teams-manifest-report-portal-bot-1.0.2.json
```

## 更新 Teams App 的操作

1. 打开 Teams Developer Portal。
2. 进入 `Apps`。
3. 找到 `Report Portal Bot`。
4. 进入 `App package editor`。
5. 打开 `manifest.json`。
6. 用 `teams-manifest-report-portal-bot-1.0.2.json` 的内容替换。
7. 保存。
8. 进入 `App validation`。
9. 点 `Start validation`。
10. 通过后点 `Publish`，提交到组织。
11. Teams 管理中心里把 App 保持为 `Unblocked`，并且 `Available to: Everyone`。

## 部署代码到服务器

在阿里云服务器执行：

```bash
cd /opt/report-portal
git pull
```

后端重启：

```bash
systemctl restart report-portal-backend
curl -s https://julongtongchuan.icu/report-portal/api/health
```

看到下面结果才算后端正常：

```json
{"status":"ok"}
```

前端重新打包并发布：

```bash
cd /opt/report-portal/frontend
npm ci
npm run build
rm -rf /var/www/report-portal
mkdir -p /var/www/report-portal
cp -r dist/* /var/www/report-portal/
systemctl reload nginx
```

## 测试 1：网页直达某个指数

浏览器打开：

```text
https://julongtongchuan.icu/report-portal/indicator?index=agri
```

应该默认选中“农业”。

再打开：

```text
https://julongtongchuan.icu/report-portal/indicator?index=futures
```

应该默认选中“期货”。

如果这一步不对，说明前端没有更新成功。

## 测试 2：Teams Bot 能不能主动发消息

在服务器执行：

```bash
cd /opt/report-portal/backend
. .venv/bin/activate

python3 <<'PY'
from app.db import SessionLocal
from app.models import TeamsBotConversation
from app.services.teams_bot import send_text_message

db = SessionLocal()
target = db.query(TeamsBotConversation).order_by(TeamsBotConversation.last_seen_at.desc()).first()
print("target:", target.id if target else None)
print("name:", target.name if target else None)
print("type:", target.conversation_type if target else None)

if not target:
    raise SystemExit("没有 Teams 目标。先在 Teams 里给 Bot 发一条消息，或者把 Bot 加到频道并 @ 它。")

print(send_text_message(target, "Report Portal Bot 手动测试消息"))
PY
```

Teams 收到消息，说明 Bot 凭证和主动发送正常。

如果报 `invalid_client`，就是 `.env` 里的 `TEAMS_BOT_APP_PASSWORD` 不是 Client secret value。

## 测试 3：测试某个指数通知

进入系统：

```text
https://julongtongchuan.icu/report-portal/indicator
```

进入：

```text
配置管理 -> 通知配置 -> 指标 Bot 定时通知
```

选择一个指数，比如“农业”：

1. 选择 Teams 目标。
2. 设置小时和分钟。
3. 勾选启用。
4. 保存。
5. 点测试。

预期结果：

1. Teams 收到一张 `农业 指标通知` 卡片。
2. 卡片里有按钮。
3. 点击按钮后，在 Teams 里打开 `指数看板`。
4. 页面默认选中“农业”。

## 测试 4：测试定时发送

把某个指数的发送时间设置成当前时间后 2 分钟。

例如现在是 16:30，就设置成：

```text
16:32
```

保存并启用后等待。

如果到时间没发：

```bash
journalctl -u report-portal-backend -n 120 --no-pager
```

重点看有没有：

```text
Teams Bot token
Teams Bot 发送失败
Index notification
```

## 如果点击还是打开浏览器

按顺序查：

1. Teams App 有没有加 `staticTabs`。
2. App 版本是不是已经发布到组织，比如 `1.0.2`。
3. Teams 管理中心 App 是否已经批准并且可用。
4. 用户是否已经安装新版 App。
5. 通知卡片里是不是按钮，不是纯文本链接。
6. 服务器 `.env` 里的 `TEAMS_APP_ID` 是否是 manifest 的 `id`。

如果 App 已发布到组织后，深链接提示找不到 App，可以把 `TEAMS_APP_ID` 改成 Teams 管理中心里该 App 的组织目录 ID，再重启后端。

## 结论

代码侧需要三件事：

1. 后端生成 Teams App 深链接。
2. Bot 卡片用按钮打开深链接。
3. 前端读取 Teams 的 `subEntityId` 并选中对应指数。

Teams 侧需要两件事：

1. Manifest 增加 `staticTabs`。
2. 发布并批准新版 App，让用户或频道安装新版 App。

