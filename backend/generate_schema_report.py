"""
生成 DWD 层表结构 HTML 报告
运行方式：cd backend && python generate_schema_report.py
输出：docs/dwd_schema_report.html
"""

from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")

from sqlalchemy import inspect as sa_inspect, UniqueConstraint
from app.db import Base
import app.models  # noqa: F401 — register all models

# ─── 元数据：表的中文描述 ────────────────────────────────────────────────────

TABLE_META: dict[str, dict] = {
    # ── DIM 主数据层 ──
    "dim_company":   {"cn": "公司",           "dept": "主数据", "module": "组织架构"},
    "dim_site":      {"cn": "园区/Estate",    "dept": "主数据", "module": "组织架构"},
    "dim_factory":   {"cn": "工厂",           "dept": "主数据", "module": "组织架构"},
    "dim_division":  {"cn": "小区/Afdeling",  "dept": "主数据", "module": "组织架构"},
    "dim_blok":      {"cn": "地块/Blok",      "dept": "主数据", "module": "组织架构"},
    # ── DWD 农业 — 铲果与产量
    "dwd_agri_harvest_daily":                   {"cn": "铲果日产量",              "dept": "农业", "module": "铲果"},
    "dwd_agri_production_target_monthly":        {"cn": "月度产量目标(BBC+预算)",   "dept": "农业", "module": "铲果"},
    "dwd_agri_akp_density_daily":               {"cn": "AKP 铲果密度",            "dept": "农业", "module": "铲果"},
    "dwd_agri_harvest_loss_daily":              {"cn": "铲果损失检查",             "dept": "农业", "module": "铲果"},
    "dwd_agri_harvest_rotation_monthly":        {"cn": "铲果周期 Rotasi Panen",   "dept": "农业", "module": "铲果周期"},
    "dwd_agri_harvest_rotation_dist_daily":     {"cn": "铲果周期分布统计",         "dept": "农业", "module": "铲果周期"},
    # 农业 — 出勤
    "dwd_agri_attendance_daily":                {"cn": "铲果工/养护工出勤",        "dept": "农业", "module": "出勤"},
    # 农业 — 养护
    "dwd_agri_maintenance_daily":               {"cn": "养护作业（窄表）",         "dept": "农业", "module": "养护"},
    "dwd_agri_fertilization_daily":             {"cn": "施肥进度统计",             "dept": "农业", "module": "养护"},
    # 农业 — 库存
    "dwd_agri_material_inventory_daily":        {"cn": "物料库存（化肥+农药+工具）","dept": "农业", "module": "仓库"},
    "dwd_agri_oil_storage_daily":               {"cn": "园区油库出油监控",         "dept": "农业", "module": "仓库"},
    # 农业 — 机械
    "dwd_agri_equipment_daily":                 {"cn": "设备状态与维修跟踪",       "dept": "农业", "module": "机械"},
    "dwd_agri_equipment_fuel_monthly":          {"cn": "机械HM和油耗监控（月度）", "dept": "农业", "module": "机械"},
    # 农业 — 运输
    "dwd_agri_tbs_transport_daily":             {"cn": "TBS 送厂运输明细",         "dept": "农业", "module": "铲果运输"},
    "dwd_agri_harvest_plan_daily":              {"cn": "当天铲果运输计划",          "dept": "农业", "module": "铲果运输"},
    # 农业 — 其他
    "dwd_agri_rainfall_daily":                  {"cn": "降雨量日报",               "dept": "农业", "module": "降雨"},
    "dwd_agri_seedling_transport_daily":        {"cn": "每日运苗情况统计",          "dept": "农业", "module": "苗区"},
    # 工厂
    "dwd_factory_grading_daily":                {"cn": "分级报告",                 "dept": "工厂", "module": "分级"},
    "dwd_factory_weighbridge_daily":            {"cn": "地磅单",                   "dept": "工厂", "module": "地磅"},
    "dwd_factory_product_inventory_daily":      {"cn": "工厂成品库存",             "dept": "工厂", "module": "库存"},
    "dwd_factory_chemical_consumption_daily":   {"cn": "工业药剂消耗（窄表）",     "dept": "工厂", "module": "库存"},
    "dwd_factory_pom_production_daily":         {"cn": "POM 毛棕榈油厂生产",       "dept": "工厂", "module": "生产"},
    "dwd_factory_kcp_production_daily":         {"cn": "KCP 棕仁榨油厂生产",       "dept": "工厂", "module": "生产"},
    "dwd_factory_refinery_production_daily":    {"cn": "精炼与包装生产绩效",       "dept": "工厂", "module": "生产"},
}

COLUMN_DESC: dict[str, str] = {
    # 公共列
    "id": "主键", "batch_id": "批次ID（可空，手动录入时为空）",
    "batch_no": "批次号", "file_id": "文件ID（可空）",
    "source_record_id": "解析记录ID（可空）",
    "report_date": "报表日期", "department": "部门（农业/工厂）",
    "site": "园区/工厂（所有多园区聚合的核心维度）",
    "row_label": "行标签（detail/subtotal/total）",
    "quality_status": "数据质量状态", "quality_message": "质量说明",
    "created_at": "创建时间",
    # 农业通用
    "division": "小区/Afdeling", "blok": "地块/Blok",
    "luas_ha": "面积（公顷）", "luas_m2": "面积（平方米）",
    "remark": "备注",
    # 铲果产量（新模型）
    "mature_area_ha": "成熟面积（ha）",
    "actual_kg": "当日实际产量（kg）",
    "mtd_actual_kg": "月累计产量（kg）",
    "bbc_ton": "BBC月目标（吨）",
    "budget_ton": "预算月目标（吨）",
    "yield_ton_per_ha": "吨/公顷",
    # 出勤（新字段）
    "worker_type": "工种（harvester铲果工 / maintenance养护工）",
    "managed_area_ha": "管理面积（ha）",
    "required_count": "需求人数",
    "own_total": "自有员工总数",
    "contractor_total": "承包商员工总数",
    "own_present": "自有出勤人数",
    "contractor_present": "承包商出勤人数",
    "total_present": "总出勤人数",
    "leave_count": "请假人数",
    "annual_leave_count": "休假人数",
    "sick_count": "病假人数",
    "absent_count": "旷工人数",
    # 养护（窄表）
    "work_type": "作业类型（pruning/weeding_cpt/lalang_control/selective_spray）",
    "daily_completed_ha": "当日完成面积（ha）",
    "mtd_completed_ha": "月累计完成面积（ha）",
    # 物料库存（合并表）
    "material_category": "物料类别（fertilizer化肥 / pesticide农药 / tools工具）",
    "opening_stock": "期初库存",
    "daily_inbound": "当日入库量",
    "daily_outbound": "当日出库量",
    "closing_stock": "期末库存（关闭库存）",
    # 油库（按油罐）
    "tank_code": "油罐编码（tank1/tank2/drum）",
    "reading_time": "读数时间（morning/evening）",
    "reading_value": "测量读数",
    "stock_liters": "库存升数",
    "actual_outbound_liters": "实际出库量（升）",
    "system_outbound_liters": "系统出库量（升）",
    # 工厂药剂（窄表）
    "chemical_code": "药剂编码",
    "chemical_name": "药剂名称",
    "consumption_qty": "消耗量",
    # 分级（计数而非百分比）
    "source_company": "来源公司",
    "source_estate_division": "来源园区+小区",
    "unripe_count": "生果数",
    "under_ripe_count": "欠熟果数",
    "ripe_count": "熟果数",
    "over_ripe_count": "过熟果数",
    "empty_bunch_count": "空果串数",
    "parthenocarpic_count": "刺猬果数",
    "dura_count": "杜拉果数",
    "long_stalk_count": "长柄果数",
    "small_fruit_count": "幼果数",
    "rotten_count": "腐烂果数",
    # 设备
    "equipment_category": "设备类别",
    "equipment_code": "设备编号",
    "equipment_type": "设备类型",
    "equipment_model": "设备型号",
    "is_normal": "是否正常（true/false）",
    "is_working": "是否作业（true/false）",
    "has_maintenance": "是否保养（true/false）",
    "damage_description": "损坏描述",
    "repair_location": "维修地点",
    "breakdown_time": "故障时间",
    "estimated_repair_time": "预计修复时间",
    "repair_status": "维修状态",
    "downtime_days": "停机天数",
    "calibration_hm_per_liter": "校准油耗（hm/升）",
    # 铲果周期分布（面积区间）
    "d_le8_area_ha": "≤8天面积（ha）",
    "d_le8_bloks": "≤8天地块数",
    "d9_10_area_ha": "9-10天面积（ha）",
    "d9_10_bloks": "9-10天地块数",
    "d11_15_area_ha": "11-15天面积（ha）",
    "d11_15_bloks": "11-15天地块数",
    "d16_20_area_ha": "16-20天面积（ha）",
    "d16_20_bloks": "16-20天地块数",
    "d21_25_area_ha": "21-25天面积（ha）",
    "d21_25_bloks": "21-25天地块数",
    "d_gt25_area_ha": ">25天面积（ha）",
    "d_gt25_bloks": ">25天地块数",
    # 降雨
    "rainfall_mm": "当日降雨量（mm）", "mtd_rainfall_mm": "月累计降雨量（mm）",
    "rain_start_time": "降雨开始时间", "rain_end_time": "降雨结束时间",
    "duration_minutes": "持续时间（分钟）",
    # 施肥
    "daily_target_kg": "当日目标施肥量（kg）", "daily_actual_kg": "当日实际施肥量（kg）",
    "daily_completion_pct": "当日完成率（%）", "mtd_target_kg": "月累计目标（kg）",
    "mtd_actual_kg": "月累计实际（kg）", "mtd_completion_pct": "月累计完成率（%）",
    "monthly_target_area_ha": "本月目标施肥面积（ha）", "monthly_target_kg": "本月目标施肥量（kg）",
    "monthly_completion_pct": "本月目标完成率（%）",
    # 库存通用
    "material_code": "物料编码", "site_code": "园区编码",
    "material_type_code": "物料类型编码", "material_name": "物料名称",
    "unit": "计量单位", "total_stock": "总库存",
    "factory_stock": "工厂库存", "g10_stock": "G10库位库存",
    "estate_stock": "园区库存", "daily_out": "当日出库量",
    "stock_qty": "库存数量",
    "material_group": "物料组", "storage_location": "库位",
    "physical_stock": "实物库存",
    # 养护工作
    "maintenance_area_ha": "养护面积（ha）",
    "pruning_daily_ha": "铲叶当日（ha）", "pruning_mtd_ha": "铲叶累计（ha）",
    "weeding_cpt_daily_ha": "全面除草当日（ha）", "weeding_cpt_mtd_ha": "全面除草累计（ha）",
    "lalang_control_daily_ha": "Lalang控制当日（ha）", "lalang_control_mtd_ha": "Lalang控制累计（ha）",
    "selective_spray_daily_ha": "选择性打药当日（ha）", "selective_spray_mtd_ha": "选择性打药累计（ha）",
    # 油库
    "tank1_reading": "油罐1测量值", "tank2_reading": "油罐2测量值",
    "tank1_stock": "油罐1库存", "tank2_stock": "油罐2库存",
    "drum_stock": "桶装油库存", "sap_book_stock": "SAP账面库存",
    "stock_vs_sap_diff": "实际与SAP差异",
    "inbound_qty": "入库量", "actual_outbound": "实际出库量",
    "system_outbound": "系统出库量", "outbound_diff": "出库量差异",
    # 损失
    "inspector": "检查人员", "bjr_kg": "平均果重BJR（kg）",
    "harvested_bunches": "铲果串数", "harvested_weight_kg": "铲果重量（kg）",
    "lost_bunches": "损失果串数", "lost_bunch_weight_kg": "损失果串重量（kg）",
    "lost_loose_fruit_count": "损失果粒数", "lost_loose_fruit_weight_kg": "损失果粒重量（kg）",
    "bunch_loss_pct": "果串损失率（%）", "loose_fruit_loss_pct": "果粒损失率（%）",
    "total_loss_pct": "总损失率（%）", "prev_loss_pct": "上次损失率（%）",
    "loss_change_pct": "损失率变化（%）",
    "ditch_bunches": "沟内遗留果串数", "ditch_weight_kg": "沟内遗留果重（kg）",
    "rotten_bunches": "树上腐烂果串数", "rotten_weight_kg": "树上腐烂果重（kg）",
    "fresh_loose_count": "新鲜果粒数", "fresh_loose_weight_kg": "新鲜果粒重量（kg）",
    "black_loose_count": "黑果粒数", "black_loose_weight_kg": "黑果粒重量（kg）",
    # 机械油耗
    "equipment_type": "设备类型", "equipment_code": "设备编号",
    "hm_value": "HM值（工时/里程）", "fuel_liters": "油耗（升）",
    "total_hm": "合计HM", "total_fuel": "合计油耗",
    "hm_per_liter": "单升作业量", "calibration_value": "审计校准值",
    "variance_pct": "实际vs校准差异（%）",
    # 设备状态
    "equipment_category": "设备类别", "equipment_model": "设备型号",
    "is_normal": "是否正常", "is_working": "是否作业",
    "damage_description": "损坏描述", "repair_location": "维修地点",
    "breakdown_time": "故障时间", "estimated_repair_time": "预计修复时间",
    "repair_status": "维修状态", "downtime_days": "停机天数",
    "has_maintenance": "是否保养",
    # 铲果周期
    "maturity_stage": "成熟阶段", "planting_year": "种植年份",
    "area_ha": "地块面积（ha）", "palm_count": "棕榈棵数",
    "sph": "株/公顷", "yph": "年累计单公顷产量",
    "prev_month_days_since_harvest": "上月末距上次铲果天数",
    "current_days_since_harvest": "当前距上次铲果天数",
    "current_round_harvested_ha": "本轮铲果面积（ha）",
    "mtd_harvested_ha": "月累计铲果面积（ha）",
    "harvest_round_count": "铲果轮次数",
    # 铲果周期分布
    "total_area_ha": "总面积（ha）", "total_bloks": "地块总数",
    "d8_area_ha": "≤8天面积（ha）", "d8_bloks": "≤8天地块数", "d8_pct": "≤8天占比（%）",
    "d9_10_area_ha": "9-10天面积（ha）", "d9_10_bloks": "9-10天地块数", "d9_10_pct": "9-10天占比（%）",
    "d11_15_area_ha": "11-15天面积（ha）","d11_15_bloks": "11-15天地块数","d11_15_pct": "11-15天占比（%）",
    "d16_20_area_ha": "16-20天面积（ha）","d16_20_bloks": "16-20天地块数","d16_20_pct": "16-20天占比（%）",
    "d21_25_area_ha": "21-25天面积（ha）","d21_25_bloks": "21-25天地块数","d21_25_pct": "21-25天占比（%）",
    # TBS运输
    "destination_factory": "送达工厂", "trip_no": "车次编号",
    "driver_name": "司机姓名", "license_plate": "车牌号",
    "vehicle_code": "车辆内部编号", "source_division": "来源小区",
    "spb_no": "收果/送果单号SPB", "bunch_count": "果串数",
    "loose_fruit_kg": "散果重量（kg）", "seal_time": "封签完成时间",
    "security_depart_time": "离开安检岗时间", "weighbridge_time": "工厂过磅时间",
    "weighbridge_kg": "过磅重量（kg）",
    # 运输计划
    "harvest_area_ha": "铲果面积（ha）", "akp_value": "AKP值",
    "leftover_h1_kg": "H+1剩果量（kg）", "leftover_h2_kg": "H+2剩果量（kg）",
    "leftover_h3_kg": "H+3剩果量（kg）", "total_leftover_kg": "剩果合计（kg）",
    "planned_harvest_kg": "预计铲果量（kg）", "planned_total_transport_kg": "预计运输总量（kg）",
    "planned_trips": "预计车次数", "planned_delivery_time": "预计送达时间",
    "leftover_remark": "剩果说明",
    # 运苗
    "transport_purpose": "运苗用途", "destination_site": "目的园区",
    "destination_blok": "目的地块", "mris_no": "MRIS运输单号",
    "daily_qty": "当日运苗数量", "cumulative_qty": "累计运苗数量",
    # 地磅
    "ticket_no": "票据号", "direction": "进/出方向",
    "transaction_type": "交易类型", "product": "产品",
    "vehicle": "车辆", "customer": "客户/目的地",
    "transporter": "运输公司", "gross_weight_kg": "毛重（kg）",
    "tare_weight_kg": "皮重（kg）", "netto_kg": "净重（kg）",
    "out_items": "带出物品",
    # 分级
    "company": "公司/PT", "company_code": "公司代码",
    "estate_division": "园区+小区", "unripe_pct": "生果（%）",
    "under_ripe_pct": "欠熟果（%）", "ripe_pct": "熟果（%）",
    "over_ripe_pct": "过熟果（%）", "empty_bunch_pct": "空果串（%）",
    "parthenocarpic_pct": "刺猬果（%）", "dura_pct": "杜拉果（%）",
    "brondolan_kg": "果粒重量（kg）", "long_stalk_pct": "长柄果（%）",
    "small_fruit_pct": "幼果（%）", "rotten_pct": "腐烂果（%）",
    "deduction_pct": "扣重比例（%）", "rejected_kg": "退回重量（kg）",
    "rejected_pct": "退回比例（%）",
    "weight_before_grading_ton": "分级前重量（吨）",
    "weight_after_grading_ton": "分级后重量（吨）",
    "total_deduction_kg": "总扣重（kg）",
    # 工业药剂
    "caustic_soda_kg": "烧碱（kg）", "aluminium_sulfate_kg": "硫酸铝（kg）",
    "aero_asc_kg": "AERO ASC（kg）", "salt_kg": "盐（kg）",
    "polymer_kg": "聚合物（kg）", "scf_kg": "SCF（kg）",
    "oxifite_kg": "除氧剂（kg）", "gr_kg": "GR药剂（kg）",
    "ps05_kg": "PS05（kg）",
    # 工厂库存
    "product_type": "产品类型（CPO/PKE等）",
    "product_spec": "产品规格", "storage_location": "储存位置",
    "tank_no": "罐号/仓号", "capacity": "罐容/仓容",
    "actual_stock": "实际库存", "ffa_pct": "FFA酸价（%）",
    "moisture_pct": "水分（%）", "impurity_pct": "杂质（%）",
    "eom_forecast_stock": "预计月底库存",
    "next_month_production_est": "下月产量预估",
    "safety_stock_days": "安全库存天数",
    # 工厂生产通用
    "period_type": "统计周期（today/monthly）",
    "responsible_person": "负责人",
    "processing_hours": "加工小时数",
    "hourly_throughput": "小时处理量",
    "efficiency_pct": "运行效率（%）",
    "downtime_hours": "停机小时数",
    "downtime_pct": "停机率（%）",
    "downtime_reason": "停机原因",
    # POM
    "own_ffb_before_kg": "自有园FFB扣重前（kg）",
    "own_ffb_after_kg": "自有园FFB扣重后（kg）",
    "plasma_ffb_before_kg": "Plasma FFB扣重前（kg）",
    "plasma_ffb_after_kg": "Plasma FFB扣重后（kg）",
    "group_ffb_before_kg": "集团FFB扣重前（kg）",
    "group_ffb_after_kg": "集团FFB扣重后（kg）",
    "external_ffb_before_kg": "外部FFB扣重前（kg）",
    "external_ffb_after_kg": "外部FFB扣重后（kg）",
    "ffb_processed_before_kg": "FFB加工量扣重前（kg）",
    "ffb_processed_after_kg": "FFB加工量扣重后（kg）",
    "ffb_balance_kg": "FFB结余（kg）",
    "cpo_production_kg": "CPO产量（kg）",
    "cpo_oe_before_pct": "CPO出油率扣重前（%）",
    "cpo_oe_after_pct": "CPO出油率扣重后（%）",
    "cpo_pao_oe_before_pct": "CPO+PAO出油率扣重前（%）",
    "cpo_pao_oe_after_pct": "CPO+PAO出油率扣重后（%）",
    "cpo_ffa_pct": "CPO FFA（%）", "cpo_moisture_pct": "CPO水分（%）",
    "cpo_impurity_pct": "CPO杂质（%）", "cpo_loss_pct": "CPO损耗率（%）",
    "kernel_production_kg": "Kernel产量（kg）",
    "kernel_oe_before_pct": "Kernel得率扣重前（%）",
    "kernel_oe_after_pct": "Kernel得率扣重后（%）",
    "kernel_moisture_pct": "Kernel水分（%）",
    "kernel_impurity_pct": "Kernel杂质（%）",
    "kernel_loss_pct": "Kernel损耗率（%）",
    "shell_production_kg": "壳产量（kg）", "shell_oe_pct": "壳得率（%）",
    "pao_blend_kg": "PAO调和量（kg）", "pao_production_kg": "PAO产量（kg）",
    "pao_pct": "PAO比例（%）",
    "cpo_sales_kg": "CPO销售量（kg）", "miko_sales_kg": "MIKO销售量（kg）",
    "kernel_sales_kg": "Kernel销售量（kg）",
    # KCP
    "own_pk_before_kg": "自有PK扣重前（kg）", "own_pk_after_kg": "自有PK扣重后（kg）",
    "group_pk_before_kg": "集团PK扣重前（kg）", "group_pk_after_kg": "集团PK扣重后（kg）",
    "external_pk_before_kg": "外部PK扣重前（kg）", "external_pk_after_kg": "外部PK扣重后（kg）",
    "total_pk_before_kg": "PK收料合计扣重前（kg）", "total_pk_after_kg": "PK收料合计扣重后（kg）",
    "pk_processed_before_kg": "PK加工量扣重前（kg）", "pk_processed_after_kg": "PK加工量扣重后（kg）",
    "pk_balance_kg": "PK结余（kg）", "pko_production_kg": "PKO产量（kg）",
    "pko_oe_before_pct": "PKO出油率扣重前（%）", "pko_oe_after_pct": "PKO出油率扣重后（%）",
    "pko_ffa_pct": "PKO FFA（%）", "pko_moisture_pct": "PKO水分（%）",
    "pko_impurity_pct": "PKO杂质（%）",
    "line1_oil_loss_pct": "1号线油损（%）", "line2_oil_loss_pct": "2号线油损（%）",
    "pke_production_kg": "PKE产量（kg）", "pke_bags": "PKE袋数",
    "pke_oe_before_pct": "PKE得率扣重前（%）", "pke_oe_after_pct": "PKE得率扣重后（%）",
    "external_crude_meal_kg": "外部粗粕（kg）",
    "pko_sales_kg": "PKO销售量（kg）", "pke_sales_kg": "PKE销售量（kg）",
    # 精炼
    "cpo_low_acid_input_kg": "CPO低酸原料（kg）",
    "cpo_high_acid_input_kg": "CPO高酸原料（kg）",
    "cpko_input_kg": "CPKO原料（kg）", "olein_input_kg": "Olein原料（kg）",
    "stearin_input_kg": "Stearin原料（kg）", "rbdpo_input_kg": "RBDPO原料（kg）",
    "rbdst_tank_input_kg": "RBDST罐区投入（kg）", "rbdpol_tank_input_kg": "RBDPOL罐区投入（kg）",
    "total_input_kg": "原料投入合计（kg）",
    "rbdpo_production_kg": "RBDPO产量（kg）", "rbdpko_production_kg": "RBDPKO产量（kg）",
    "pfad_production_kg": "PFAD产量（kg）", "pkfad_production_kg": "PKFAD产量（kg）",
    "rbdol_production_kg": "RBDOL产量（kg）", "rbdst_production_kg": "RBDST产量（kg）",
    "oilku_1l_production_kg": "Oilku 1L产量（kg）", "oilku_2l_production_kg": "Oilku 2L产量（kg）",
    "total_production_kg": "产品产量合计（kg）",
    "unit_processing_cost": "单位加工成本", "yield_pct": "原料得率（%）",
    "rbdpo_sales_kg": "RBDPO销售量（kg）",
    "rbdpo_sales_pu_kg": "RBDPO销至PT.PU（kg）",
    "rbdpo_sales_asp_kg": "RBDPO销至PT.ASP（kg）",
    "rbdpko_sales_kg": "RBDPKO销售量（kg）",
    "pfad_sales_kg": "PFAD销售量（kg）", "pkfad_sales_kg": "PKFAD销售量（kg）",
    "rbdol_sales_kg": "RBDOL销售量（kg）", "rbdst_sales_kg": "RBDST销售量（kg）",
    "total_sales_kg": "销售总量（kg）",
    "oilku_1l_sales_kg": "Oilku 1L销售量（kg）", "oilku_2l_sales_kg": "Oilku 2L销售量（kg）",
    # 产量监控（已有表）
    "bbc_ton": "月目标BBC（吨）", "actual_today_ton": "当日实际产量（吨）",
    "actual_to_date_ton": "月累计产量（吨）",
    "actual_vs_bbc_percent": "完成率/BBC（%）",
    "remaining_bbc_ton": "BBC剩余目标（吨）",
    "remaining_effective_days": "剩余有效天数",
    "daily_target_ton": "日目标产量（吨）",
    "confidence": "解析置信度",
    # AKP
    "sap": "SAP编号", "tt_year": "种植年份",
    "panen_count": "铲果次数", "akp_percent": "AKP密度（%）",
    "panen_kg": "产量（kg）", "jumlah_janjang": "果串数",
    "tk_panen": "铲果工人数", "keterangan": "备注",
    # 出勤
    "section": "统计区段", "worker_type": "工种（harvester/maintenance）",
    "afdeling": "小区/Afdeling", "kebutuhan_pemanen": "需求人数",
    "actual_pemanen": "实际人数", "actual_vs_kebutuhan": "实际vs需求",
    "hadir": "出勤人数", "hadir_percent": "出勤率（%）",
    "ijin": "请假人数", "ijin_percent": "请假率（%）",
    "cuti": "休假人数", "cuti_percent": "休假率（%）",
    "sakit": "病假人数", "sakit_percent": "病假率（%）",
    "mangkir": "旷工人数", "mangkir_percent": "旷工率（%）",
    "total_karyawan": "总员工数", "total_percent": "合计百分比",
    # 预算
    "mature_area_ha": "成熟面积（ha）",
    "budget_sep_ton": "9月预算（吨）", "budget_oct_ton": "10月预算（吨）",
    "budget_nov_ton": "11月预算（吨）", "budget_dec_ton": "12月预算（吨）",
    "budget_jan_ton": "1月预算（吨）", "budget_feb_ton": "2月预算（吨）",
    "budget_mar_ton": "3月预算（吨）", "budget_apr_ton": "4月预算（吨）",
    "budget_may_ton": "5月预算（吨）", "budget_jun_ton": "6月预算（吨）",
    "budget_jul_ton": "7月预算（吨）", "budget_aug_ton": "8月预算（吨）",
    "annual_budget_ton": "年度预算（吨）", "yield_ton_per_ha": "吨/公顷",
    # 预估
    "estimated_harvest_area_ha": "预计铲果面积（ha）",
    "estimated_production_kg": "预计产量（kg）",
}

TYPE_MAP = {
    "INTEGER": "int", "VARCHAR": "str", "TEXT": "text",
    "FLOAT": "float", "DATE": "date", "DATETIME": "datetime", "BOOLEAN": "bool",
}

COMMON_COLS = {"id", "batch_id", "batch_no", "file_id", "source_record_id",
               "report_date", "department", "site", "row_label",
               "quality_status", "quality_message", "created_at"}

DEPT_COLOR = {"农业": "#1b6b5f", "工厂": "#c98a1c"}


def get_col_type(col) -> str:
    t = str(col.type.__class__.__name__).upper()
    return TYPE_MAP.get(t, t.lower())


def get_unique_constraints(table) -> list[list[str]]:
    ucs = []
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            ucs.append([c.name for c in constraint.columns])
    return ucs


def build_tables() -> list[dict]:
    tables = []
    registry = {m.class_.__tablename__: m for m in Base.registry.mappers
                if m.class_.__tablename__.startswith("dwd_")}
    order = [t for t in TABLE_META if t in registry]
    for tname in order:
        mapper = registry[tname]
        meta = TABLE_META[tname]
        table_obj = mapper.persist_selectable
        cols = table_obj.columns
        ucs = get_unique_constraints(table_obj)
        uk_cols = set(c for uc in ucs for c in uc)

        common, domain = [], []
        for col in cols:
            n = col.name
            entry = {
                "name": n,
                "type": get_col_type(col),
                "nullable": col.nullable,
                "default": str(col.default.arg) if col.default and not callable(col.default.arg) else "",
                "desc": COLUMN_DESC.get(n, ""),
                "is_uk": n in uk_cols,
                "is_pk": col.primary_key,
            }
            if n in COMMON_COLS:
                common.append(entry)
            else:
                domain.append(entry)

        tables.append({
            "name": tname, "cn": meta["cn"], "dept": meta["dept"],
            "module": meta["module"], "ucs": ucs,
            "common": common, "domain": domain,
            "total_cols": len(cols),
        })
    return tables


def render_html(tables: list[dict]) -> str:
    by_dept: dict[str, dict[str, list]] = {}
    for t in tables:
        by_dept.setdefault(t["dept"], {}).setdefault(t["module"], []).append(t)

    total_cols = sum(t["total_cols"] for t in tables)
    dept_counts = {d: sum(len(ms) for ms in mods.values())
                   for d, mods in by_dept.items()}

    # nav links
    nav_items = []
    for dept, modules in by_dept.items():
        for mod in modules:
            nav_items.append(f'<a href="#{dept}-{mod}">{dept}·{mod}</a>')
    nav_html = "\n".join(nav_items)

    # summary cards
    card = lambda label, val: f'<div class="card"><div class="label">{label}</div><div class="value">{val}</div></div>'
    cards_html = "".join([
        card("DWD 表数量", len(tables)),
        card("字段总数", total_cols),
        card("农业报表", dept_counts.get("农业", 0)),
        card("工厂报表", dept_counts.get("工厂", 0)),
    ])

    # table sections
    sections_html = ""
    for dept, modules in by_dept.items():
        color = DEPT_COLOR.get(dept, "#333")
        for mod, tbls in modules.items():
            anchor = f"{dept}-{mod}"
            table_htmls = ""
            for t in tbls:
                # unique constraint badges
                uk_badges = " ".join(
                    f'<span class="uk-badge">({", ".join(uc)})</span>'
                    for uc in t["ucs"]
                )

                def col_rows(cols, section_class=""):
                    rows = ""
                    for c in cols:
                        uk_mark = '<span class="uk-star" title="唯一约束字段">🔑</span>' if c["is_uk"] else ""
                        pk_mark = '<span class="pk-star" title="主键">PK</span>' if c["is_pk"] else ""
                        null_badge = '<span class="null-badge">可空</span>' if c["nullable"] else '<span class="notnull-badge">必填</span>'
                        rows += f"""
                        <tr class="{section_class}">
                          <td>{pk_mark}{uk_mark}<code>{c["name"]}</code></td>
                          <td><span class="type-badge type-{c['type']}">{c['type']}</span></td>
                          <td>{null_badge}</td>
                          <td>{c['desc'] or '<span class="no-desc">—</span>'}</td>
                        </tr>"""
                    return rows

                domain_rows = col_rows(t["domain"])
                common_rows = col_rows(t["common"], "common-row")

                table_htmls += f"""
                <div class="table-block" id="tbl-{t['name']}">
                  <div class="table-header">
                    <div class="table-title-group">
                      <span class="table-cn">{t['cn']}</span>
                      <code class="table-name">{t['name']}</code>
                    </div>
                    <div class="table-meta-right">
                      <span class="col-count">{t['total_cols']} 字段</span>
                    </div>
                  </div>
                  <div class="uk-section">
                    <span class="uk-label">唯一约束：</span>{uk_badges if uk_badges else '<span class="no-desc">（无）</span>'}
                  </div>
                  <div class="table-scroll">
                    <table>
                      <thead>
                        <tr><th style="width:220px">字段名</th><th style="width:80px">类型</th><th style="width:70px">可空</th><th>含义</th></tr>
                      </thead>
                      <tbody>
                        <tr class="section-sep"><td colspan="4"><span>业务字段（{len(t['domain'])}个）</span></td></tr>
                        {domain_rows}
                        <tr class="section-sep"><td colspan="4"><span>公共字段（{len(t['common'])}个）</span></td></tr>
                        {common_rows}
                      </tbody>
                    </table>
                  </div>
                </div>"""

            sections_html += f"""
            <section id="{anchor}">
              <div class="section-head" style="border-left:4px solid {color}">
                <span class="dept-tag" style="background:{color}">{dept}</span>
                <h2>{mod}</h2>
                <span class="mod-count">{len(tbls)} 张表</span>
              </div>
              {table_htmls}
            </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>DWD 层表结构文档</title>
  <style>
    :root{{--bg:#f4f6f9;--panel:#fff;--ink:#1f2933;--muted:#6b7a8d;--line:#dde3ec;
          --head:#f0f4f8;--green:#1b6b5f;--gold:#c98a1c;--red:#c53030;--accent:#2563eb}}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;font-size:13.5px;
          background:var(--bg);color:var(--ink);line-height:1.55}}
    a{{color:var(--accent);text-decoration:none}}
    /* ── header ── */
    header{{position:sticky;top:0;z-index:20;background:var(--panel);
            border-bottom:1px solid var(--line);padding:14px 24px 10px;
            box-shadow:0 2px 8px rgba(0,0,0,.06)}}
    .header-top{{display:flex;align-items:baseline;gap:14px}}
    h1{{font-size:20px;font-weight:700}}
    .subtitle{{color:var(--muted);font-size:12px}}
    nav{{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap}}
    nav a{{padding:4px 10px;border:1px solid var(--line);border-radius:20px;
           font-size:12px;background:#f8fafc;color:var(--muted);transition:.15s}}
    nav a:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
    /* ── main ── */
    main{{padding:22px 28px 60px;max-width:1320px;margin:0 auto}}
    /* ── summary ── */
    .cards{{display:flex;gap:14px;margin-bottom:28px;flex-wrap:wrap}}
    .card{{background:var(--panel);border:1px solid var(--line);border-radius:8px;
           padding:14px 20px;min-width:130px}}
    .card .label{{color:var(--muted);font-size:12px}}
    .card .value{{font-size:30px;font-weight:700;color:var(--green);margin-top:4px}}
    /* ── section ── */
    section{{margin-bottom:32px}}
    .section-head{{display:flex;align-items:center;gap:10px;padding:12px 16px;
                   background:var(--panel);border-radius:8px 8px 0 0;
                   border:1px solid var(--line);margin-bottom:0}}
    .section-head h2{{font-size:15px;font-weight:700}}
    .dept-tag{{color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px}}
    .mod-count{{margin-left:auto;color:var(--muted);font-size:12px}}
    /* ── table block ── */
    .table-block{{background:var(--panel);border:1px solid var(--line);
                  border-top:none;padding:0}}
    .table-block+.table-block{{border-top:2px solid var(--bg)}}
    .table-header{{display:flex;align-items:center;justify-content:space-between;
                   padding:10px 16px 6px;background:#fafcff}}
    .table-title-group{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
    .table-cn{{font-size:14px;font-weight:700;color:var(--ink)}}
    .table-name{{font-size:11.5px;color:var(--muted);background:#f0f4f8;
                 padding:2px 7px;border-radius:4px}}
    .col-count{{font-size:11.5px;color:var(--muted);background:#eef2f8;
                padding:2px 8px;border-radius:10px}}
    /* ── uk section ── */
    .uk-section{{padding:5px 16px 8px;font-size:12px;color:var(--muted);
                 display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
    .uk-label{{font-weight:600}}
    .uk-badge{{background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;
               padding:1px 7px;border-radius:4px;font-family:monospace;font-size:11px}}
    /* ── table ── */
    .table-scroll{{overflow-x:auto}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{background:var(--head);padding:7px 10px;text-align:left;font-size:11.5px;
        font-weight:700;color:var(--muted);border-bottom:1px solid var(--line);
        white-space:nowrap;text-transform:uppercase;letter-spacing:.04em}}
    td{{padding:6px 10px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}}
    tr:hover td{{background:#fafcff}}
    /* section separator */
    .section-sep td{{background:#f8fafc;padding:5px 10px;border-bottom:1px solid var(--line)}}
    .section-sep span{{font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em}}
    .common-row td{{background:#fdfefe;color:#374151}}
    /* badges */
    .type-badge{{font-size:11px;padding:1px 6px;border-radius:4px;font-family:monospace;font-weight:600}}
    .type-int{{background:#ede9fe;color:#5b21b6}}
    .type-float{{background:#dcfce7;color:#166534}}
    .type-str{{background:#dbeafe;color:#1e40af}}
    .type-text{{background:#fef9c3;color:#713f12}}
    .type-date{{background:#fce7f3;color:#9d174d}}
    .type-datetime{{background:#ffe4e6;color:#9f1239}}
    .type-bool{{background:#e0f2fe;color:#0c4a6e}}
    .null-badge{{font-size:10.5px;color:var(--muted);background:#f1f5f9;
                 padding:1px 6px;border-radius:4px}}
    .notnull-badge{{font-size:10.5px;color:#92400e;background:#fef3c7;
                    padding:1px 6px;border-radius:4px;font-weight:600}}
    .uk-star{{font-size:11px;margin-right:3px}}
    .pk-star{{font-size:10px;background:#fde68a;color:#78350f;padding:0 4px;
              border-radius:3px;margin-right:4px;font-weight:700}}
    .no-desc{{color:#cbd5e1}}
    code{{font-family:"Consolas","Cascadia Code",monospace;font-size:12.5px}}
    /* footer */
    footer{{text-align:center;padding:24px;color:var(--muted);font-size:12px}}
    @media print{{
      header{{position:static}} nav,.col-count{{display:none}}
      main{{padding:0;max-width:none}} section{{break-inside:avoid}}
      .table-scroll{{overflow:visible}}
    }}
  </style>
</head>
<body>
<header>
  <div class="header-top">
    <h1>DWD 层表结构文档</h1>
    <span class="subtitle">数据中台门户 · 自动生成 · {__import__('datetime').date.today()}</span>
  </div>
  <nav>{nav_html}</nav>
</header>
<main>
  <div class="cards">{cards_html}</div>
  {sections_html}
</main>
<footer>由 generate_schema_report.py 自动生成 · 基于 SQLAlchemy 模型</footer>
</body>
</html>"""


if __name__ == "__main__":
    tables = build_tables()
    html = render_html(tables)
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "dwd_schema_report.html")
    out = os.path.normpath(out)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: {out}")
    print(f"  {len(tables)} tables, {sum(t['total_cols'] for t in tables)} columns")
