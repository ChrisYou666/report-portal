# 解析健壮性设计方案

---

## 一、问题分析

### 当前方案的根本缺陷

现在 OCR 解析用硬编码像素坐标定位列：

```python
columns = [("division", 80), ("luas_ha", 175), ("bbc_ton", 265), ...]
```

图片只要稍微放大/缩小/旋转，整列就错位。PaddleOCR 只识别文字位置，不理解表格语义，后续的坐标映射逻辑需要人工维护每种模板。

### 新增方案：Vision LLM

接入视觉大模型（DeepSeek-VL、Claude claude-haiku-4-5 等），直接把图片发给 LLM，让它理解表格结构并返回结构化 JSON，完全跳过坐标映射。

---

## 二、解析方案对比

| 方案 | 适用格式 | 准确率 | 成本 | 速度 | 隐私 |
|---|---|---|---|---|---|
| **Vision LLM**（新，推荐） | 图片、PDF | ⭐⭐⭐⭐⭐ | 按 token 计费 | 2-5 秒/张 | 图片发送到外部 API |
| Excel 表头关键词匹配 | Excel | ⭐⭐⭐⭐⭐ | 免费 | 极快 | 本地处理 |
| 动态表头 + PaddleOCR | 图片 | ⭐⭐⭐ | 免费 | 1-3 秒/张 | 本地处理 |
| PDF 文字提取（pdfplumber） | 数字 PDF | ⭐⭐⭐⭐ | 免费 | 极快 | 本地处理 |
| 硬编码坐标（现有） | 图片 | ⭐⭐ | 免费 | 快 | 本地处理 |

**结论：图片和扫描 PDF 用 Vision LLM，Excel 和数字 PDF 继续本地处理。**

---

## 三、Vision LLM 方案设计

### 3.1 处理流程

```
图片 / 扫描 PDF
    ↓
（PDF 先转图片：pdf2image）
    ↓
调用 Vision LLM API
  发送：图片 + 结构化提取 Prompt
    ↓
返回 JSON（报表类型 + 数据行）
    ↓
校验 JSON 结构
    ↓
写入 DWD（与现有 upsert 逻辑一致）
    ↓
LLM 调用失败？→ 降级到 PaddleOCR + 动态表头检测
```

### 3.2 Prompt 设计

```python
SYSTEM_PROMPT = """
你是农业生产数据提取助手。从图片中提取表格数据，严格按 JSON 格式返回，不要输出其他内容。

支持的报表类型及字段：

production_monitoring（产量监控日报）:
  division, luas_ha, bbc_ton, actual_today_ton, actual_to_date_ton,
  actual_vs_bbc_percent, remaining_bbc_ton, remaining_effective_days, daily_target_ton

akp_density（AKP 铲果密度）:
  division, blok, sap, luas_ha, tt_year, panen_count,
  akp_percent, panen_kg, jumlah_janjang, tk_panen, keterangan

harvester_attendance（铲果工/养护工出勤）:
  section, worker_type, afdeling, luas_ha, kebutuhan_pemanen, actual_pemanen,
  hadir, hadir_percent, ijin, cuti, sakit, mangkir, total_karyawan

production_budget（月度生产预算）:
  division, mature_area_ha, budget_sep_ton ~ budget_aug_ton, annual_budget_ton

production_estimate（产量预估）:
  division, mature_area_ha, estimated_harvest_area_ha, estimated_production_kg, akp_percent
"""

USER_PROMPT = """
请从这张图片中提取农业报表数据，返回以下 JSON 格式：

{
  "report_type": "production_monitoring | akp_density | harvester_attendance | production_budget | production_estimate | unknown",
  "confidence": 0.0-1.0,
  "rows": [
    { "row_label": "detail | subtotal | total", ...字段 }
  ],
  "notes": "可选备注，如识别困难的地方"
}

数字字段返回数值类型（不含单位和逗号），无法识别的字段返回 null。
"""
```

### 3.3 LLM 提供商选择

| 提供商 | 模型 | 优势 | 成本 | 数据隐私 |
|---|---|---|---|---|
| **本地 Ollama** | **qwen2.5-vl:7b**（推荐） | 零费用；数据不出本地；中文/印尼语优秀；RTX 5060（8GB）可运行 | 免费 | ✅ 完全本地 |
| 本地 Ollama | minicpm-v:8b | 更小，推理更快 | 免费 | ✅ 完全本地 |
| Anthropic API | claude-haiku-4-5-20251001 | 准确率最高，备用云端选项 | ~$0.003/张 | 图片发外部 |
| DeepSeek API | deepseek-vl2 | 成本低 | ~$0.001/张 | 图片发外部 |
| 阿里云 API | qwen-vl-plus | 国内合规 | ~$0.002/张 | 国内服务器 |

**推荐默认：本地 Ollama + qwen2.5-vl:7b**

```bash
# 一次性安装，之后常驻后台
ollama pull qwen2.5-vl:7b
ollama serve   # 监听 http://localhost:11434
```

RTX 5060（8GB VRAM）运行 qwen2.5-vl:7b（4-bit 量化）约占 4.5GB，推理一张图约 2-4 秒，完全够用。

**云端 API 作为备用**：本地服务不可用时自动切换，保证高可用。提供商通过配置项切换，代码层统一用 OpenAI 兼容接口。

### 3.4 代码结构

```python
# backend/app/services/vision_parser.py

class VisionParser:
    def __init__(self, provider: str = "claude"):
        self.provider = provider  # claude | deepseek | openai | qwen

    def parse_image(self, image_path: Path) -> VisionParseResult:
        """发送图片给 LLM，返回结构化结果"""
        response = self._call_api(image_path)
        return self._validate_and_parse(response)

    def _call_api(self, image_path: Path) -> str:
        if self.provider == "claude":
            return self._call_claude(image_path)
        elif self.provider == "deepseek":
            return self._call_deepseek(image_path)
        # ...

    def _validate_and_parse(self, raw: str) -> VisionParseResult:
        """校验 JSON 结构，字段类型转换"""
        ...
```

### 3.5 成本控制

- 只对图片和扫描 PDF 调用 Vision LLM，Excel 和数字 PDF 本地处理
- 图片压缩到 1200px 宽（保留可读性，减少 token）
- 批次内多张图片并发调用，减少等待时间
- 记录每次调用的 token 消耗，在 admin 面板展示月度费用

---

## 四、各格式完整策略

### Excel（最高优先级，最可靠，本地处理）

按列名匹配，完全不依赖位置：

```python
# 找表头行，建立「列名 → 列序号」映射
header_map = find_header_row(ws, known_headers={
    "division": ["DIVISI", "小区", "区"],
    "bbc_ton":  ["BBC", "TARGET"],
    "actual_today_ton": ["HARIAN", "当日"],
})
# 按名称读取，与列顺序无关
division = row[header_map["division"]]
```

### 图片 JPG/PNG（Vision LLM 优先，PaddleOCR 兜底）

```
图片
  ├─ 调用 Vision LLM → JSON                    （主路径）
  │   失败/超时/结果置信度 < 0.6
  └─ PaddleOCR + 动态表头检测 → 结构化数据     （降级路径）
      失败
      └─ 硬编码坐标映射                         （最终兜底）
```

### PDF（两段式）

```
PDF
  ├─ pdfplumber 提取文字表格（数字 PDF）       → Excel 同款列名匹配
  └─ 提取失败（扫描件）
      └─ pdf2image 转 PNG → 走图片路径（Vision LLM）
```

---

## 五、模板配置

每类报表的表头关键词集中配置，方便维护和新增：

```python
TEMPLATE_HEADERS = {
    "production_monitoring": {
        "division":                 ["DIVISI", "小区", "区"],
        "luas_ha":                  ["LUAS", "面积"],
        "bbc_ton":                  ["BBC"],
        "actual_today_ton":         ["HARIAN", "当日实际"],
        "actual_to_date_ton":       ["MTD", "月累计"],
        "remaining_effective_days": ["SISA HARI", "剩余天数"],
    },
    "akp_density": {
        "division":    ["DIVISI", "小区"],
        "blok":        ["BLOK", "块"],
        "luas_ha":     ["LUAS", "面积"],
        "akp_percent": ["AKP%"],
        "panen_kg":    ["PANEN KG", "产量"],
    },
    # ...
}
```

---

## 六、实施顺序

| 步骤 | 工作量 | 收益 | 优先级 |
|---|---|---|---|
| 1. Excel 按列名匹配 | 小（2-3天） | Excel 准确率接近 100% | 🔴 最高 |
| 2. Vision LLM 接入 | 中（3-5天） | 图片/扫描 PDF 准确率大幅提升 | 🔴 最高 |
| 3. PDF 文字提取 | 小（1-2天） | 新增数字 PDF 支持 | 🟡 中 |
| 4. PaddleOCR 动态表头 | 中（3-5天） | 离线兜底更稳定 | 🟢 低（有 LLM 后优先级下降） |
| 5. 配置化模板定义 | 小（1天） | 方便新增报表类型 | 🟡 中 |

---

## 七、数据质量标注

解析完成后在写入 DWD 时记录置信度：

```python
# Vision LLM 返回的 confidence < 0.7，或降级到 OCR 路径
quality_status = "low_confidence"
quality_message = f"Vision LLM 置信度 {confidence:.2f}，建议人工核对"
```

前端报表中低置信度行用黄色标注，不拒绝写入（保持高可用）。

---

## 八、新增配置项

```env
# .env

# 主路径：本地 Ollama（推荐）
VISION_PARSER_ENABLED=true
VISION_PARSER_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-vl:7b

# 备用：云端 API（本地不可用时自动切换）
VISION_FALLBACK_PROVIDER=claude        # claude | deepseek | none
ANTHROPIC_API_KEY=sk-ant-...           # 备用 Claude API Key
DEEPSEEK_API_KEY=sk-...               # 备用 DeepSeek API Key

# 通用参数
VISION_MAX_IMAGE_WIDTH=1200            # 压缩宽度，减少推理时间
VISION_CONFIDENCE_THRESHOLD=0.6       # 低于此值降级到 PaddleOCR
```
