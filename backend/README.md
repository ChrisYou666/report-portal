# Backend

后端使用 FastAPI，负责报表上传、批次状态、AI 解析、报表生成、推送和指标查询接口。

## 本地启动

```powershell
cd report-collection-portal\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 当前接口

- `GET /api/health`：健康检查
- `POST /api/uploads`：上传一个批次，可包含多个文件
- `GET /api/batches`：查看批次列表
- `GET /api/batches/{batch_no}`：查看批次详情
- `POST /api/batches/{batch_no}/parse`：AI 解析流程
- `POST /api/batches/{batch_no}/generate-report`：生成 HTML 报表流程
- `POST /api/batches/{batch_no}/push`：按配置推送到 Teams / WhatsApp
- `GET /api/query/metrics`：自定义指标查询接口

## OneDrive / SharePoint 文件归档

上传报表时，后端会先保存一份本地副本；当 `ONEDRIVE_ENABLED=true` 时，再上传到配置的 SharePoint 文档库。

云端目录规则：

```text
{ONEDRIVE_ROOT_FOLDER}/{year}/{month}/{day}/{site}/{batch_no}/{filename}
```

示例：

```text
报表原始文件/2026/05/25/中加/B20260525103000A1B2/机械HM.xlsx
```

`.env` 需要配置：

```env
ONEDRIVE_ENABLED=true
ONEDRIVE_TENANT_ID=
ONEDRIVE_CLIENT_ID=
ONEDRIVE_CLIENT_SECRET=
ONEDRIVE_SITE_ID=
ONEDRIVE_DRIVE_ID=
ONEDRIVE_ROOT_FOLDER=报表原始文件
ONEDRIVE_PATH_TEMPLATE={year}/{month}/{day}/{site}/{batch_no}
KEEP_LOCAL_COPY=true
```

当前使用 Microsoft Graph 小文件上传接口，适合常规 Excel、PDF、Word、图片等报表文件。
