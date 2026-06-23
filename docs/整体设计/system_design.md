# 数据中台门户 — 整体设计文档

> 状态：核心方向已确认，表单字段待业务梳理
> 最后更新：2026-05-28

---

## 一、业务背景

棕榈农业公司，在印尼运营多个园区（当前：七园、八园）。现场人员每日填报生产、出勤、密度等数据，管理层需要汇总报表进行决策。

**核心痛点：**
- 数据分散在 Excel 文件和 SAP 系统中，无法实时汇总
- 报表制作依赖人工，耗时且易出错
- 管理层获取数据需要反复沟通
- 园区部分区域网络不稳定，影响数据录入

**目标：**
- 建立统一的数据采集入口（云端表单录入 + 文件上传）
- 构建标准化数据仓库（ODS → DIM → DWD → DWS）
- 自动生成并推送日报给管理层，超时自动告警
- 自研数据查询与可视化（含 Chat BI 中印双语自然语言查询）

---

## 二、用户角色与核心需求

| 角色 | 典型用户 | 核心需求 | 主要使用场景 |
|---|---|---|---|
| 现场操作人员 | 园区一线员工（印尼语） | 简单快速填报；无网络时本地缓存，有网络时自动上传 | 每天填写产量、AKP、出勤，手机操作，印尼语界面 |
| 园区管理层 | 园区经理、主管 | 实时查看本园区完成情况，接收每日推送 | 每天收 WhatsApp/Teams 推送；数据迟报时收到告警 |
| 公司管理层 | 总部管理者 | 跨园区汇总对比，快速提问获取数据 | 推送日报图片；Chat BI 中文自然语言查询 |
| 数据/IT 团队 | 内部数据人员 | 维护系统、配置推送规则、监控数据管道 | 管理后台、SAP 同步、数据质量监控 |

---

## 三、数据架构

### 3.1 数据来源

| 来源 | 类型 | 采集方式 | 频率 |
|---|---|---|---|
| 现场人员填报 | 产量监控、AKP 密度、出勤 | 有网云端提交；无网本地存储，恢复后自动同步 | 每日 |
| 文件上传 | 历史数据导入、特殊格式 | 标准 Excel 模板上传；非标准格式用 Vision LLM 解析 | 按需 |
| SAP 系统 | 实际产量、月度预算、BBC 目标 | 定时同步脚本（SQL Server → PostgreSQL），目标支持 SAP 直推 | 每日/每月 |

> **历史数据导入**：SAP 数据约 80GB，报表数据约 100GB，需支持批量导入，分批处理。

### 3.2 数据分层

```
【ODS 原始层】— 原样镜像，不做任何转换
  ods.sap_stg_zest_blockc    实际产量原始数据
  ods.sap_stg_zest_blockb    月度预算原始数据
  ods.sap_stg_zest_blockp    BBC 目标原始数据
  ods.sap_stg_zest_block     地块主数据
  ods.sap_stg_zest_division  小区主数据

【DIM 维度层】— 主数据，相对稳定
  dim.sap_estate             园区/庄园
  dim.sap_division           小区
  dim.sap_block              地块
  （待建）dim.employee        员工

【DWD 明细层】— 业务事实，按业务主键 upsert，后提交覆盖前
  ✅ dwd_production_monitoring_daily   产量监控日报（小区粒度）
  ✅ dwd_akp_density_daily             AKP 铲果密度（地块粒度）
  ✅ dwd_harvester_attendance_daily    铲果工/养护工出勤
  ✅ dwd_production_budget_monthly     月度生产预算
  ✅ dwd_production_estimate_daily     产量预估
  ❌ dwd_crop_loss_daily               铲果损耗（待建，数据源待梳理）
  ❌ dwd_harvest_rotation_daily        收获轮换（待建，数据源待梳理）
  ❌ dwd_monthly_cost                  月度成本（待建，数据源待梳理）

【DWS 汇总层】— 跨来源聚合，每日重建，供前端和报表直接使用
  ✅ dws.harvest_production_daily_summary  产量监控汇总（已有，需去掉 DROP-RECREATE）
  ❌ dws.attendance_daily_summary          出勤汇总（待建）
  ❌ dws.akp_density_summary               AKP 汇总（待建）
  ❌ dws.budget_vs_actual_monthly          预算 vs 实际对比（待建）

【ADS 应用层】— 按需建视图，不存实体表
  为前端查询、Chat BI、API 导出提供优化视图
```

---

## 四、应用架构

### 4.1 前端页面规划

```
数据中台门户（React SPA + PWA，中印双语）
│
├── 工作台 Dashboard
│     - KPI 总览：今日总产量、出勤率、待同步条数、迟报告警数
│     - 录入进度：今日各园区各表单提交状态（已交/未交/已逾期）
│     - 快捷入口
│
├── 数据录入（待建）
│     - 云端表单 + 离线缓存，全页面印尼语支持
│     - Tab 1: 产量监控日报      → dwd_production_monitoring_daily
│     - Tab 2: AKP 铲果密度      → dwd_akp_density_daily
│     - Tab 3: 铲果工/养护工出勤 → dwd_harvester_attendance_daily
│     - Tab 4: （后续扩展）
│     - 离线状态条：待同步 N 条 / 全部已同步
│
├── 文件上传
│     - 标准模板下载（每类报表提供 Excel 模板）
│     - 标准模板上传（按固定列名解析，高准确率）
│     - 非标准格式上传（Vision LLM 解析）
│     - 历史数据批量导入
│
├── 批次流程
│     - 上传批次状态追踪
│     - 解析进度监控，支持重新解析
│
├── 日报管理
│     - 查看已生成报表（HTML / XLSX / PNG）
│     - 手动触发生成/推送
│     - 推送规则配置（推送时间、节假日排除、超时告警阈值）
│     - 推送历史记录
│
├── 数据查询
│     - 多维分析（覆盖所有 DWD 表）
│     - 按日期/园区/小区/地块/人员类型筛选
│     - 趋势图、汇总表
│     - 导出 Excel/PDF
│     - Chat BI：中印双语自然语言提问 → AI 生成 SQL → 返回结果（后期）
│
└── 系统管理
      ├── 用户管理（已有）
      ├── 推送规则配置（待建）
      ├── 园区/部门配置（待建）
      └── 数据管道监控（待建）
```

### 4.2 后端 API 规划

```
/api/auth/*          认证（已有）
/api/users/*         用户管理（已有）
/api/uploads         文件上传（已有）
/api/batches/*       批次管理（已有）
/api/reports/*       报表管理（已有）
/api/query/*         数据查询（已有，待扩展）

/api/entry/*         数据录入（待建）
  POST /entry/production-monitoring   产量监控提交
  POST /entry/akp-density             AKP 密度提交
  POST /entry/attendance              出勤提交
  POST /entry/batch-sync              批量同步（离线队列上传）
  GET  /entry/options                 录入选项（园区/小区/员工等）
  GET  /entry/status                  今日各园区录入状态

/api/push-rules/*    推送规则（待建）
  GET/PUT /push-rules/{report_type}   读取/更新推送配置
    配置项：推送触发方式、截止时间、节假日规则、超时告警阈值

/api/admin/*         管理接口（待建）
  GET  /admin/pipeline-status         数据管道状态
  POST /admin/sap-sync                手动触发 SAP 同步
  GET  /admin/data-quality            数据质量报告

/api/chat/*          Chat BI（后期）
  POST /chat/query                    自然语言（中/印）→ SQL → 结果
```

---

## 五、关键设计决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 录入方式 | 云端表单为主，文件上传为辅 | 表单直接入库准确率 100%；上传处理历史数据和特殊格式 |
| Excel 上传策略 | 提供标准模板下载；标准模板按固定列名解析；非标准走 Vision LLM | 简单可靠；兼顾历史遗留文件 |
| 权限范围 | 上传员只能操作自己 User 表里配置的 department/site | 人员有规定的数据范围，系统强制执行 |
| 离线策略 | Offline-First：本地 IndexedDB 存储，有网自动同步 | 园区部分区域无网络，不能阻塞录入 |
| 移动端 | PWA，不做独立 App | 无需应用商店发布；支持"添加到主屏幕" |
| 多语言 | 全系统中印双语，现场操作人员默认印尼语 | 现场员工为印尼语用户 |
| DWS 重建 | 去掉 DROP-RECREATE，改为 TRUNCATE + INSERT | 避免重建期间前端查询返回空 |
| 推送方式 | 数据完整后自动触发；可配置截止时间；超时发告警 | 管理层不手动触发；迟报可见 |
| 节假日配置 | 每类报表单独配置是否排除节假日 | 不同业务类型规则不同 |
| BI 工具 | 自研（门户内置查询 + Chat BI），不依赖 Tableau/Power BI | 避免高额授权费；数据不出内网 |
| Chat BI | 后期接入本地 LLM（Ollama）做 Text-to-SQL，支持中印双语 | 零 API 费用；数据不出本地 |
| 解析策略 | Excel 标准模板固定列名；图片/扫描 PDF 用本地 Vision LLM（Ollama + Qwen2.5-VL:7b）；失败降级到云端 API → PaddleOCR | 详见 parsing_robustness_design.md |

---

## 六、离线录入架构

### 核心流程

```
现场人员填表提交
    ↓
写入本地 IndexedDB（立即成功，不依赖网络）
    ↓
UI 显示「待同步 N 条」
    ↓
检测到网络恢复（或用户手动点击同步）
    ↓
调用 POST /api/entry/batch-sync 批量上传
    ↓
服务器按业务主键 upsert 写入 DWD
    ↓
本地标记为「已同步」
```

### 技术选型

| 技术 | 用途 |
|---|---|
| IndexedDB（idb 库） | 本地持久化，浏览器关闭后不丢失 |
| Service Worker | 离线时页面正常打开；缓存静态资源 |
| Background Sync API | 网络恢复自动触发（Android Chrome 支持） |
| PWA Manifest | 支持添加到主屏幕 |

### 记录状态机

```
draft → pending → syncing → synced
                          ↘ failed（可手动重试）
```

### iOS 特殊处理

iOS Safari 不支持 Background Sync，需在 App 启动时自动检测网络并触发同步，顶部提示待同步条数。

### 冲突规则

同一业务主键（日期 + 园区 + 小区）在多设备均有提交时，以**最后上传时间**为准覆盖，与 DWD upsert 策略一致。

### 实施顺序

1. 先做在线版本（表单直接提交服务器）
2. 叠加离线层（IndexedDB 队列 + 同步 UI）
3. 配置 PWA（Service Worker + Manifest）

---

## 七、推送与告警规则

### 推送触发逻辑

```
数据完整（当日所有必填表单已提交）
    ↓
立即触发生成报表 → 推送 WhatsApp/Teams
    ↓
若到达截止时间仍未完整
    ↓
发出迟报告警（推送告警消息到管理层）
```

### 可配置项（每类报表独立配置）

| 配置项 | 示例 | 说明 |
|---|---|---|
| 截止时间 | 每日 14:00 | 超过此时间触发告警 |
| 告警升级时间 | 每日 16:00 | 再次告警，抄送上级 |
| 节假日排除 | 是/否 | 部分报表节假日不需要提交 |
| 推送目标 | Teams 频道、WhatsApp 群 | 可多目标 |

---

## 八、开发路线图

### 阶段一：基础框架（✅ 已完成）
- ✅ 文件上传 + AI 解析 + 批次管理
- ✅ DWD 5 张表 + 业务主键唯一约束（ON CONFLICT DO UPDATE）
- ✅ 产量监控日报生成（HTML / XLSX / PNG）
- ✅ Teams / WhatsApp 推送
- ✅ JWT 认证 + 4 角色权限框架
- ✅ 用户管理页面

### 阶段二：数据录入表单（近期，最高优先级）

> 前置条件：需先与业务方确认各报表的录入字段

**2a — 在线版本**
- [ ] 确认各报表字段（与业务方对齐）
- [ ] 产量监控日报录入表单（中印双语）
- [ ] AKP 铲果密度录入表单（中印双语）
- [ ] 铲果工/养护工出勤录入表单（中印双语）
- [ ] 表单提交直接写 DWD
- [ ] 权限范围校验（只能录入自己 department/site 的数据）
- [ ] 工作台「今日录入状态」模块
- [ ] 手机端响应式适配

**2b — 离线能力**
- [ ] IndexedDB 本地队列（idb 库）
- [ ] 网络状态检测 + 自动/手动同步
- [ ] 同步状态 UI（待同步 N 条、同步中、失败重试）
- [ ] PWA Manifest + Service Worker

### 阶段三：数据管道完善（中期）
- [ ] 标准 Excel 模板生成与下载
- [ ] 标准模板上传解析（固定列名）
- [ ] Vision LLM 接入（Ollama + Qwen2.5-VL:7b）处理非标准格式
- [ ] DWS 层去掉 DROP-RECREATE
- [ ] SAP 定时同步自动化（每日 cron）
- [ ] 推送规则可配置化（截止时间、节假日、告警升级）
- [ ] 历史数据批量导入工具
- [ ] 扩展 DWD：损耗、轮换、成本（待数据源梳理后）

### 阶段四：分析与消费（后期）
- [ ] 数据查询扩展至所有 DWD 表
- [ ] 导出 Excel / PDF
- [ ] 跨园区对比报表
- [ ] 数据质量监控面板
- [ ] Chat BI：中印双语自然语言查询（本地 LLM Text-to-SQL）

---

## 九、待确认问题

> 仅列出尚未明确的问题

1. **录入表单字段**：各报表需要录入哪些字段？这是最关键的，需与业务方逐表梳理，影响阶段二所有工作。
2. **损耗/成本/轮换数据源**：这三类数据目前由谁负责填写、来自哪个系统，是否纳入本系统管理。
3. **SAP 直推可行性**：SAP 系统是否支持主动推送数据到外部系统（Webhook/API），还是只能被动拉取？
