# 问题积压清单

## 🔴 高优先级

### P1-1 OCR 列映射靠硬编码像素坐标
**位置**: `backend/app/services/parser.py` — `add_production_monitoring_records` 等 5 个函数
**问题**: `columns = [("division", 80), ("luas_ha", 175), ...]` 用像素 x 坐标定位列，图片大小/打印机/拍摄角度稍有变化就错位
**方案**: 改为动态表头检测（见 `parsing_robustness_design.md`）
**影响**: 所有 OCR 解析结果的准确性

### P1-2 DWD 数据质量无感知
**位置**: `backend/app/services/parser.py` — `load_dwd_*` 函数
**问题**: `confidence` 字段写入数据库但从未用于过滤或标注，低置信度数据直接进报表
**方案**: confidence < 0.7 打标 `quality_status = 'low_confidence'`，报表中标注
**影响**: 报表数值可信度

### P1-3 DWS 层 DROP-RECREATE 模式
**位置**: `scripts/build_harvest_production_summary.py` — `build_summary()`
**问题**: 每次生成报表 `DROP TABLE IF EXISTS ... CREATE TABLE AS ...`，重建期间查询返回空，数据量大后性能差
**方案**: 改为 `TRUNCATE + INSERT` 或增量 upsert
**影响**: 并发访问时报表页面短暂空白

---

## 🟡 中优先级

### P2-1 PDF 无法解析
**位置**: `backend/app/services/parser.py` — `detect_parser_type()`
**问题**: PDF 被标为 `unsupported` 跳过，但业务上 PDF 是主要格式之一
**方案**: 数字 PDF 用 pdfplumber 提取表格；扫描 PDF 转图片再 OCR（见设计文档）
**影响**: PDF 格式报表全部无法入库

### P2-2 ETL 脚本未接入系统
**位置**: `ETLs/` 目录下 9 个 SQL 文件
**问题**: 损耗、成本、轮换等业务数据的 ETL 脚本存在但从未被调用，对应 DWD 表也未定义
**方案**: 阶段 2 逐步接入（见建设规划）
**影响**: 数据中台覆盖率低

### P2-3 DWS 只有产量日报一张汇总表
**位置**: `scripts/build_harvest_production_summary.py`
**问题**: dws 层只有 `harvest_production_daily_summary`，出勤/AKP/损耗/成本均无汇总
**方案**: 阶段 2 补充 `attendance_daily_summary`、`akp_summary` 等
**影响**: QueryPage 无法查询大部分数据域

### P2-4 解析失败原因不细化
**位置**: `backend/app/services/parser.py` — `parse_file()`
**问题**: 失败统一记为 `parse_failed`，无法区分是 OCR 引擎问题、列映射问题还是数据质量问题
**方案**: 拆分为 `parse_failed_ocr` / `parse_failed_mapping` / `parse_failed_quality`

### P2-5 权限硬编码
**位置**: `backend/app/api/uploads.py`
**问题**: `AUTHORIZED_UPLOADERS = ["王浩源", "张杰铭", "王云豪"]` 硬编码，无法动态管理
**方案**: 移到数据库或配置文件，或实现简单 RBAC

---

## 🟢 低优先级

### P3-1 QueryPage 查询覆盖不全
**位置**: `frontend/src/pages/QueryPage.tsx` + `backend/app/api/query.py`
**问题**: 只支持 akp_density 和 attendance 查询，production_monitoring/budget/estimate 不可查
**方案**: 扩展 query API 支持所有 DWD 表

### P3-2 无结构化日志
**问题**: 解析过程、API 请求无结构化日志，生产排错困难
**方案**: 接入 Python logging，关键操作记录 batch_no + 耗时 + 状态

### P3-3 SAP 同步未自动化
**位置**: `scripts/sync_sap_stg_to_ods.py`
**问题**: SAP 数据同步需手动执行脚本，没有定时任务
**方案**: 接入 cron 或 FastAPI BackgroundScheduler

### P3-4 无数据血缘追溯 API
**问题**: 无法从前端追溯某条 DWD 记录来自哪个批次的哪个文件的第几行
**方案**: `GET /api/batches/{batch_no}/dwd-records` 接口

---

## 已解决

- ✅ DWD upsert 改为 `INSERT ... ON CONFLICT DO UPDATE`（业务主键覆盖）
- ✅ 唯一约束添加到 5 张 DWD 表
- ✅ 批次详情改为弹窗
- ✅ 今日上传数量统计修复
- ✅ 页面切换不重新加载数据（hidden 属性）
- ✅ 生成报表文件名去掉 batch_no（同名覆盖）
- ✅ 上传后自动触发解析
- ✅ 批次流程去掉生成/推送操作
- ✅ 重新解析按钮支持已成功解析的批次
