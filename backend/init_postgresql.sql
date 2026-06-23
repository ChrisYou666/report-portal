-- ============================================================
-- PostgreSQL 初始化脚本
-- 数据库：report_portal
-- 使用前请先创建数据库和用户：
--   CREATE USER portal WITH PASSWORD 'your_password';
--   CREATE DATABASE report_portal OWNER portal;
--   \c report_portal
--   \i init_postgresql.sql
-- ============================================================

\set ON_ERROR_STOP on

BEGIN;

-- ════════════════════════════════════════════════════════════
-- 上传与解析层
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS upload_batches (
    id          SERIAL       PRIMARY KEY,
    batch_no    VARCHAR(40)  NOT NULL,
    report_name VARCHAR(160) NOT NULL,
    report_type VARCHAR(40)  NOT NULL,
    department  VARCHAR(120) NOT NULL,
    site        VARCHAR(120) NOT NULL DEFAULT '',
    factory     VARCHAR(120) NOT NULL DEFAULT '',
    report_date DATE         NOT NULL,
    uploader    VARCHAR(120) NOT NULL,
    remark      TEXT         NOT NULL DEFAULT '',
    status      VARCHAR(40)  NOT NULL DEFAULT 'uploaded',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_upload_batches_batch_no UNIQUE (batch_no)
);
CREATE INDEX IF NOT EXISTS ix_upload_batches_batch_no ON upload_batches(batch_no);

CREATE TABLE IF NOT EXISTS upload_files (
    id                   SERIAL       PRIMARY KEY,
    batch_id             INTEGER      NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    original_filename    VARCHAR(255) NOT NULL,
    stored_path          VARCHAR(500) NOT NULL,
    file_size            INTEGER      NOT NULL,
    file_type            VARCHAR(30)  NOT NULL,
    detected_report_name VARCHAR(160) NOT NULL DEFAULT '',
    status               VARCHAR(40)  NOT NULL DEFAULT 'uploaded',
    created_at           TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_upload_files_batch_id ON upload_files(batch_id);

CREATE TABLE IF NOT EXISTS parsed_documents (
    id            SERIAL       PRIMARY KEY,
    batch_id      INTEGER      NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    file_id       INTEGER      NOT NULL REFERENCES upload_files(id)   ON DELETE CASCADE,
    parser_type   VARCHAR(40)  NOT NULL,
    source_path   VARCHAR(500) NOT NULL,
    raw_text      TEXT         NOT NULL DEFAULT '',
    raw_json      TEXT         NOT NULL DEFAULT '',
    status        VARCHAR(40)  NOT NULL DEFAULT 'parsed',
    error_message TEXT         NOT NULL DEFAULT '',
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_parsed_documents_batch_id ON parsed_documents(batch_id);
CREATE INDEX IF NOT EXISTS ix_parsed_documents_file_id  ON parsed_documents(file_id);

CREATE TABLE IF NOT EXISTS parsed_structured_records (
    id                 SERIAL           PRIMARY KEY,
    parsed_document_id INTEGER          NOT NULL REFERENCES parsed_documents(id) ON DELETE CASCADE,
    batch_id           INTEGER          NOT NULL REFERENCES upload_batches(id)   ON DELETE CASCADE,
    file_id            INTEGER          NOT NULL REFERENCES upload_files(id)     ON DELETE CASCADE,
    template_name      VARCHAR(160)     NOT NULL DEFAULT '',
    record_type        VARCHAR(80)      NOT NULL DEFAULT '',
    row_index          INTEGER          NOT NULL DEFAULT 0,
    record_json        TEXT             NOT NULL DEFAULT '',
    confidence         DOUBLE PRECISION,
    created_at         TIMESTAMP        NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_parsed_structured_records_parsed_document_id ON parsed_structured_records(parsed_document_id);
CREATE INDEX IF NOT EXISTS ix_parsed_structured_records_batch_id           ON parsed_structured_records(batch_id);
CREATE INDEX IF NOT EXISTS ix_parsed_structured_records_file_id            ON parsed_structured_records(file_id);

CREATE TABLE IF NOT EXISTS parsed_fields (
    id                 SERIAL           PRIMARY KEY,
    parsed_document_id INTEGER          NOT NULL REFERENCES parsed_documents(id) ON DELETE CASCADE,
    batch_id           INTEGER          NOT NULL REFERENCES upload_batches(id)   ON DELETE CASCADE,
    file_id            INTEGER          NOT NULL REFERENCES upload_files(id)     ON DELETE CASCADE,
    record_type        VARCHAR(40)      NOT NULL,
    sheet_name         VARCHAR(160)     NOT NULL DEFAULT '',
    row_index          INTEGER          NOT NULL DEFAULT 0,
    column_index       INTEGER          NOT NULL DEFAULT 0,
    field_name         VARCHAR(160)     NOT NULL DEFAULT '',
    field_value        TEXT             NOT NULL DEFAULT '',
    confidence         DOUBLE PRECISION,
    raw_json           TEXT             NOT NULL DEFAULT '',
    created_at         TIMESTAMP        NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_parsed_fields_parsed_document_id ON parsed_fields(parsed_document_id);
CREATE INDEX IF NOT EXISTS ix_parsed_fields_batch_id           ON parsed_fields(batch_id);
CREATE INDEX IF NOT EXISTS ix_parsed_fields_file_id            ON parsed_fields(file_id);

CREATE TABLE IF NOT EXISTS parse_jobs (
    id               SERIAL       PRIMARY KEY,
    batch_id         INTEGER      NOT NULL REFERENCES upload_batches(id) ON DELETE CASCADE,
    batch_no         VARCHAR(40)  NOT NULL,
    status           VARCHAR(40)  NOT NULL DEFAULT 'pending',
    total_files      INTEGER      NOT NULL DEFAULT 0,
    processed_files  INTEGER      NOT NULL DEFAULT 0,
    parsed_files     INTEGER      NOT NULL DEFAULT 0,
    skipped_files    INTEGER      NOT NULL DEFAULT 0,
    failed_files     INTEGER      NOT NULL DEFAULT 0,
    current_filename VARCHAR(255) NOT NULL DEFAULT '',
    message          TEXT         NOT NULL DEFAULT '',
    error_message    TEXT         NOT NULL DEFAULT '',
    started_at       TIMESTAMP,
    finished_at      TIMESTAMP,
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_parse_jobs_batch_no UNIQUE (batch_no)
);
CREATE INDEX IF NOT EXISTS ix_parse_jobs_batch_id ON parse_jobs(batch_id);
CREATE INDEX IF NOT EXISTS ix_parse_jobs_batch_no ON parse_jobs(batch_no);

-- ════════════════════════════════════════════════════════════
-- 用户与系统
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL       PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(120) NOT NULL DEFAULT '',
    role          VARCHAR(40)  NOT NULL DEFAULT 'viewer',
    department    VARCHAR(120) NOT NULL DEFAULT '',
    site          VARCHAR(120) NOT NULL DEFAULT '',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_username UNIQUE (username)
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

CREATE TABLE IF NOT EXISTS data_source_configs (
    id                SERIAL       PRIMARY KEY,
    name              VARCHAR(120) NOT NULL,
    description       TEXT         NOT NULL DEFAULT '',
    source_type       VARCHAR(40)  NOT NULL,
    host              VARCHAR(255) NOT NULL DEFAULT '',
    port              INTEGER      NOT NULL DEFAULT 5432,
    database_name     VARCHAR(120) NOT NULL DEFAULT '',
    username          VARCHAR(120) NOT NULL DEFAULT '',
    password_enc      TEXT         NOT NULL DEFAULT '',
    api_url           VARCHAR(500) NOT NULL DEFAULT '',
    api_method        VARCHAR(10)  NOT NULL DEFAULT 'GET',
    api_headers_enc   TEXT         NOT NULL DEFAULT '',
    api_response_path VARCHAR(255) NOT NULL DEFAULT '',
    sync_query        TEXT         NOT NULL DEFAULT '',
    target_entity     VARCHAR(40)  NOT NULL,
    field_mapping     TEXT         NOT NULL DEFAULT '{}',
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_sync_at      TIMESTAMP,
    last_sync_count   INTEGER      NOT NULL DEFAULT 0,
    last_sync_status  VARCHAR(40)  NOT NULL DEFAULT '',
    last_sync_message TEXT         NOT NULL DEFAULT '',
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- DIM 主数据层
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS dim_company (
    id          SERIAL       PRIMARY KEY,
    code        VARCHAR(40)  NOT NULL,
    name        VARCHAR(120) NOT NULL,
    name_id     VARCHAR(120) NOT NULL DEFAULT '',
    country     VARCHAR(60)  NOT NULL DEFAULT 'Indonesia',
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    source      VARCHAR(40)  NOT NULL DEFAULT 'manual',
    external_id VARCHAR(120) NOT NULL DEFAULT '',
    remark      TEXT         NOT NULL DEFAULT '',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dim_company_code UNIQUE (code)
);
CREATE INDEX IF NOT EXISTS ix_dim_company_code ON dim_company(code);

CREATE TABLE IF NOT EXISTS dim_site (
    id           SERIAL       PRIMARY KEY,
    company_code VARCHAR(40)  NOT NULL DEFAULT '',
    code         VARCHAR(40)  NOT NULL,
    name         VARCHAR(120) NOT NULL,
    name_id      VARCHAR(120) NOT NULL DEFAULT '',
    region       VARCHAR(120) NOT NULL DEFAULT '',
    country      VARCHAR(60)  NOT NULL DEFAULT 'Indonesia',
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    source       VARCHAR(40)  NOT NULL DEFAULT 'manual',
    external_id  VARCHAR(120) NOT NULL DEFAULT '',
    remark       TEXT         NOT NULL DEFAULT '',
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dim_site_code UNIQUE (code)
);
CREATE INDEX IF NOT EXISTS ix_dim_site_code         ON dim_site(code);
CREATE INDEX IF NOT EXISTS ix_dim_site_company_code ON dim_site(company_code);

CREATE TABLE IF NOT EXISTS dim_factory (
    id                    SERIAL           PRIMARY KEY,
    company_code          VARCHAR(40)      NOT NULL DEFAULT '',
    code                  VARCHAR(40)      NOT NULL,
    name                  VARCHAR(120)     NOT NULL,
    name_id               VARCHAR(120)     NOT NULL DEFAULT '',
    factory_type          VARCHAR(40)      NOT NULL DEFAULT '',
    location              VARCHAR(200)     NOT NULL DEFAULT '',
    capacity_ton_per_hour DOUBLE PRECISION,
    is_active             BOOLEAN          NOT NULL DEFAULT TRUE,
    source                VARCHAR(40)      NOT NULL DEFAULT 'manual',
    external_id           VARCHAR(120)     NOT NULL DEFAULT '',
    remark                TEXT             NOT NULL DEFAULT '',
    created_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dim_factory_code UNIQUE (code)
);
CREATE INDEX IF NOT EXISTS ix_dim_factory_code         ON dim_factory(code);
CREATE INDEX IF NOT EXISTS ix_dim_factory_company_code ON dim_factory(company_code);

CREATE TABLE IF NOT EXISTS dim_division (
    id           SERIAL       PRIMARY KEY,
    company_code VARCHAR(40)  NOT NULL DEFAULT '',
    site_code    VARCHAR(40)  NOT NULL,
    code         VARCHAR(40)  NOT NULL,
    name         VARCHAR(120) NOT NULL,
    name_id      VARCHAR(120) NOT NULL DEFAULT '',
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    source       VARCHAR(40)  NOT NULL DEFAULT 'manual',
    external_id  VARCHAR(120) NOT NULL DEFAULT '',
    remark       TEXT         NOT NULL DEFAULT '',
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dim_division_site_code UNIQUE (site_code, code)
);
CREATE INDEX IF NOT EXISTS ix_dim_division_company_code ON dim_division(company_code);
CREATE INDEX IF NOT EXISTS ix_dim_division_site_code    ON dim_division(site_code);
CREATE INDEX IF NOT EXISTS ix_dim_division_code         ON dim_division(code);

CREATE TABLE IF NOT EXISTS dim_blok (
    id            SERIAL           PRIMARY KEY,
    company_code  VARCHAR(40)      NOT NULL DEFAULT '',
    site_code     VARCHAR(40)      NOT NULL,
    division_code VARCHAR(40)      NOT NULL,
    code          VARCHAR(80)      NOT NULL,
    name          VARCHAR(120)     NOT NULL DEFAULT '',
    luas_ha       DOUBLE PRECISION,
    planting_year INTEGER,
    maturity_stage VARCHAR(40)     NOT NULL DEFAULT '',
    palm_count    INTEGER,
    sph           DOUBLE PRECISION,
    is_active     BOOLEAN          NOT NULL DEFAULT TRUE,
    source        VARCHAR(40)      NOT NULL DEFAULT 'manual',
    external_id   VARCHAR(120)     NOT NULL DEFAULT '',
    remark        TEXT             NOT NULL DEFAULT '',
    created_at    TIMESTAMP        NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dim_blok UNIQUE (site_code, division_code, code)
);
CREATE INDEX IF NOT EXISTS ix_dim_blok_company_code  ON dim_blok(company_code);
CREATE INDEX IF NOT EXISTS ix_dim_blok_site_code     ON dim_blok(site_code);
CREATE INDEX IF NOT EXISTS ix_dim_blok_division_code ON dim_blok(division_code);
CREATE INDEX IF NOT EXISTS ix_dim_blok_code          ON dim_blok(code);

-- ════════════════════════════════════════════════════════════
-- DWD 农业层（公共宏：batch_id / file_id / source_record_id 均可空）
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS dwd_agri_harvest_daily (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    division         VARCHAR(80)      NOT NULL DEFAULT '',
    mature_area_ha   DOUBLE PRECISION,
    actual_kg        DOUBLE PRECISION,
    mtd_actual_kg    DOUBLE PRECISION,
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_harvest_daily UNIQUE (report_date, site, division)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_daily_report_date ON dwd_agri_harvest_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_daily_site        ON dwd_agri_harvest_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_production_target_monthly (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    division         VARCHAR(80)      NOT NULL DEFAULT '',
    mature_area_ha   DOUBLE PRECISION,
    bbc_ton          DOUBLE PRECISION,
    budget_ton       DOUBLE PRECISION,
    yield_ton_per_ha DOUBLE PRECISION,
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_production_target UNIQUE (report_date, site, division)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_production_target_monthly_report_date ON dwd_agri_production_target_monthly(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_production_target_monthly_site        ON dwd_agri_production_target_monthly(site);

CREATE TABLE IF NOT EXISTS dwd_agri_akp_density_daily (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    division         VARCHAR(80)      NOT NULL DEFAULT '',
    blok             VARCHAR(80)      NOT NULL DEFAULT '',
    sap              VARCHAR(80)      NOT NULL DEFAULT '',
    luas_ha          DOUBLE PRECISION,
    tt_year          INTEGER,
    panen_count      DOUBLE PRECISION,
    akp_percent      DOUBLE PRECISION,
    panen_kg         DOUBLE PRECISION,
    jumlah_janjang   DOUBLE PRECISION,
    tk_panen         DOUBLE PRECISION,
    keterangan       VARCHAR(255)     NOT NULL DEFAULT '',
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_akp_density UNIQUE (report_date, site, division, blok)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_akp_density_daily_report_date ON dwd_agri_akp_density_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_akp_density_daily_site        ON dwd_agri_akp_density_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_harvest_loss_daily (
    id                      SERIAL           PRIMARY KEY,
    batch_id                INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                 INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id        INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date             DATE             NOT NULL,
    site                    VARCHAR(120)     NOT NULL DEFAULT '',
    division                VARCHAR(80)      NOT NULL DEFAULT '',
    blok                    VARCHAR(80)      NOT NULL DEFAULT '',
    inspector               VARCHAR(120)     NOT NULL DEFAULT '',
    bjr_kg                  DOUBLE PRECISION,
    harvested_bunches       DOUBLE PRECISION,
    harvested_weight_kg     DOUBLE PRECISION,
    lost_bunches            DOUBLE PRECISION,
    lost_bunch_weight_kg    DOUBLE PRECISION,
    lost_loose_fruit_count  DOUBLE PRECISION,
    lost_loose_fruit_weight_kg DOUBLE PRECISION,
    ditch_bunch_count       DOUBLE PRECISION,
    ditch_weight_kg         DOUBLE PRECISION,
    rotten_bunch_count      DOUBLE PRECISION,
    rotten_weight_kg        DOUBLE PRECISION,
    fresh_loose_count       DOUBLE PRECISION,
    fresh_loose_weight_kg   DOUBLE PRECISION,
    black_loose_count       DOUBLE PRECISION,
    black_loose_weight_kg   DOUBLE PRECISION,
    quality_status          VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message         TEXT             NOT NULL DEFAULT '',
    created_at              TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_harvest_loss UNIQUE (report_date, site, division, blok)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_loss_daily_report_date ON dwd_agri_harvest_loss_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_loss_daily_site        ON dwd_agri_harvest_loss_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_harvest_rotation_monthly (
    id                              SERIAL           PRIMARY KEY,
    batch_id                        INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                        VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                         INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id                INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date                     DATE             NOT NULL,
    site                            VARCHAR(120)     NOT NULL DEFAULT '',
    division                        VARCHAR(80)      NOT NULL DEFAULT '',
    blok                            VARCHAR(80)      NOT NULL DEFAULT '',
    maturity_stage                  VARCHAR(40)      NOT NULL DEFAULT '',
    planting_year                   INTEGER,
    area_ha                         DOUBLE PRECISION,
    palm_count                      DOUBLE PRECISION,
    sph                             DOUBLE PRECISION,
    yph                             DOUBLE PRECISION,
    prev_month_days_unharvested     DOUBLE PRECISION,
    current_month_days_unharvested  DOUBLE PRECISION,
    current_round_harvested_ha      DOUBLE PRECISION,
    mtd_harvested_ha                DOUBLE PRECISION,
    harvest_round_count             DOUBLE PRECISION,
    quality_status                  VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message                 TEXT             NOT NULL DEFAULT '',
    created_at                      TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_harvest_rotation UNIQUE (report_date, site, division, blok)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_rotation_monthly_report_date ON dwd_agri_harvest_rotation_monthly(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_rotation_monthly_site        ON dwd_agri_harvest_rotation_monthly(site);

CREATE TABLE IF NOT EXISTS dwd_agri_harvest_rotation_dist_daily (
    id              SERIAL           PRIMARY KEY,
    batch_id        INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no        VARCHAR(40)      NOT NULL DEFAULT '',
    file_id         INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER         REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date     DATE             NOT NULL,
    site            VARCHAR(120)     NOT NULL DEFAULT '',
    division        VARCHAR(80)      NOT NULL DEFAULT '',
    total_area_ha   DOUBLE PRECISION,
    total_bloks     DOUBLE PRECISION,
    d_le8_area_ha   DOUBLE PRECISION,
    d_le8_bloks     DOUBLE PRECISION,
    d9_10_area_ha   DOUBLE PRECISION,
    d9_10_bloks     DOUBLE PRECISION,
    d11_15_area_ha  DOUBLE PRECISION,
    d11_15_bloks    DOUBLE PRECISION,
    d16_20_area_ha  DOUBLE PRECISION,
    d16_20_bloks    DOUBLE PRECISION,
    d21_25_area_ha  DOUBLE PRECISION,
    d21_25_bloks    DOUBLE PRECISION,
    d_gt25_area_ha  DOUBLE PRECISION,
    d_gt25_bloks    DOUBLE PRECISION,
    quality_status  VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message TEXT             NOT NULL DEFAULT '',
    created_at      TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_harvest_rot_dist UNIQUE (report_date, site, division)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_rotation_dist_daily_report_date ON dwd_agri_harvest_rotation_dist_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_rotation_dist_daily_site        ON dwd_agri_harvest_rotation_dist_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_attendance_daily (
    id                 SERIAL           PRIMARY KEY,
    batch_id           INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no           VARCHAR(40)      NOT NULL DEFAULT '',
    file_id            INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id   INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date        DATE             NOT NULL,
    site               VARCHAR(120)     NOT NULL DEFAULT '',
    division           VARCHAR(80)      NOT NULL DEFAULT '',
    worker_type        VARCHAR(40)      NOT NULL DEFAULT '',
    managed_area_ha    DOUBLE PRECISION,
    required_count     DOUBLE PRECISION,
    own_total          DOUBLE PRECISION,
    contractor_total   DOUBLE PRECISION,
    own_present        DOUBLE PRECISION,
    contractor_present DOUBLE PRECISION,
    total_present      DOUBLE PRECISION,
    leave_count        DOUBLE PRECISION,
    annual_leave_count DOUBLE PRECISION,
    sick_count         DOUBLE PRECISION,
    absent_count       DOUBLE PRECISION,
    quality_status     VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message    TEXT             NOT NULL DEFAULT '',
    created_at         TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_attendance UNIQUE (report_date, site, division, worker_type)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_attendance_daily_report_date ON dwd_agri_attendance_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_attendance_daily_site        ON dwd_agri_attendance_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_maintenance_daily (
    id                  SERIAL           PRIMARY KEY,
    batch_id            INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no            VARCHAR(40)      NOT NULL DEFAULT '',
    file_id             INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id    INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date         DATE             NOT NULL,
    site                VARCHAR(120)     NOT NULL DEFAULT '',
    division            VARCHAR(80)      NOT NULL DEFAULT '',
    work_type           VARCHAR(60)      NOT NULL DEFAULT '',
    managed_area_ha     DOUBLE PRECISION,
    daily_completed_ha  DOUBLE PRECISION,
    mtd_completed_ha    DOUBLE PRECISION,
    quality_status      VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message     TEXT             NOT NULL DEFAULT '',
    created_at          TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_maintenance UNIQUE (report_date, site, division, work_type)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_maintenance_daily_report_date ON dwd_agri_maintenance_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_maintenance_daily_site        ON dwd_agri_maintenance_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_fertilization_daily (
    id                    SERIAL           PRIMARY KEY,
    batch_id              INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no              VARCHAR(40)      NOT NULL DEFAULT '',
    file_id               INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id      INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date           DATE             NOT NULL,
    site                  VARCHAR(120)     NOT NULL DEFAULT '',
    division              VARCHAR(80)      NOT NULL DEFAULT '',
    daily_target_kg       DOUBLE PRECISION,
    daily_actual_kg       DOUBLE PRECISION,
    mtd_target_kg         DOUBLE PRECISION,
    mtd_actual_kg         DOUBLE PRECISION,
    monthly_target_area_ha DOUBLE PRECISION,
    monthly_target_kg     DOUBLE PRECISION,
    quality_status        VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message       TEXT             NOT NULL DEFAULT '',
    created_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_fertilization UNIQUE (report_date, site, division)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_fertilization_daily_report_date ON dwd_agri_fertilization_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_fertilization_daily_site        ON dwd_agri_fertilization_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_material_inventory_daily (
    id                SERIAL           PRIMARY KEY,
    batch_id          INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no          VARCHAR(40)      NOT NULL DEFAULT '',
    file_id           INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id  INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date       DATE             NOT NULL,
    site              VARCHAR(120)     NOT NULL DEFAULT '',
    material_category VARCHAR(40)      NOT NULL DEFAULT '',
    material_code     VARCHAR(80)      NOT NULL DEFAULT '',
    material_name     VARCHAR(200)     NOT NULL DEFAULT '',
    unit              VARCHAR(20)      NOT NULL DEFAULT '',
    storage_location  VARCHAR(80)      NOT NULL DEFAULT '',
    opening_stock     DOUBLE PRECISION,
    daily_inbound     DOUBLE PRECISION,
    daily_outbound    DOUBLE PRECISION,
    closing_stock     DOUBLE PRECISION,
    quality_status    VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message   TEXT             NOT NULL DEFAULT '',
    created_at        TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_material_inv UNIQUE (report_date, site, material_code, storage_location)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_material_inventory_daily_report_date ON dwd_agri_material_inventory_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_material_inventory_daily_site        ON dwd_agri_material_inventory_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_oil_storage_daily (
    id                       SERIAL           PRIMARY KEY,
    batch_id                 INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                 VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                  INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id         INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date              DATE             NOT NULL,
    site                     VARCHAR(120)     NOT NULL DEFAULT '',
    tank_code                VARCHAR(20)      NOT NULL DEFAULT '',
    reading_time             VARCHAR(10)      NOT NULL DEFAULT '',
    reading_value            DOUBLE PRECISION,
    stock_liters             DOUBLE PRECISION,
    sap_book_stock           DOUBLE PRECISION,
    inbound_liters           DOUBLE PRECISION,
    actual_outbound_liters   DOUBLE PRECISION,
    system_outbound_liters   DOUBLE PRECISION,
    quality_status           VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message          TEXT             NOT NULL DEFAULT '',
    created_at               TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_oil_storage UNIQUE (report_date, site, tank_code, reading_time)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_oil_storage_daily_report_date ON dwd_agri_oil_storage_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_oil_storage_daily_site        ON dwd_agri_oil_storage_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_equipment_daily (
    id                    SERIAL           PRIMARY KEY,
    batch_id              INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no              VARCHAR(40)      NOT NULL DEFAULT '',
    file_id               INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id      INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date           DATE             NOT NULL,
    site                  VARCHAR(120)     NOT NULL DEFAULT '',
    equipment_category    VARCHAR(40)      NOT NULL DEFAULT '',
    equipment_code        VARCHAR(80)      NOT NULL DEFAULT '',
    equipment_type        VARCHAR(40)      NOT NULL DEFAULT '',
    equipment_model       VARCHAR(80)      NOT NULL DEFAULT '',
    is_normal             BOOLEAN,
    is_working            BOOLEAN,
    has_maintenance       BOOLEAN,
    damage_description    TEXT             NOT NULL DEFAULT '',
    repair_location       VARCHAR(80)      NOT NULL DEFAULT '',
    breakdown_time        VARCHAR(30)      NOT NULL DEFAULT '',
    estimated_repair_time VARCHAR(30)      NOT NULL DEFAULT '',
    repair_status         VARCHAR(40)      NOT NULL DEFAULT '',
    downtime_days         DOUBLE PRECISION,
    remark                TEXT             NOT NULL DEFAULT '',
    quality_status        VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message       TEXT             NOT NULL DEFAULT '',
    created_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_equipment UNIQUE (report_date, site, equipment_code)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_equipment_daily_report_date ON dwd_agri_equipment_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_equipment_daily_site        ON dwd_agri_equipment_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_equipment_fuel_monthly (
    id                      SERIAL           PRIMARY KEY,
    batch_id                INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                 INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id        INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date             DATE             NOT NULL,
    site                    VARCHAR(120)     NOT NULL DEFAULT '',
    equipment_type          VARCHAR(40)      NOT NULL DEFAULT '',
    equipment_code          VARCHAR(80)      NOT NULL DEFAULT '',
    hm_value                DOUBLE PRECISION,
    fuel_liters             DOUBLE PRECISION,
    calibration_hm_per_liter DOUBLE PRECISION,
    quality_status          VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message         TEXT             NOT NULL DEFAULT '',
    created_at              TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_equipment_fuel UNIQUE (report_date, site, equipment_code)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_equipment_fuel_monthly_report_date ON dwd_agri_equipment_fuel_monthly(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_equipment_fuel_monthly_site        ON dwd_agri_equipment_fuel_monthly(site);

CREATE TABLE IF NOT EXISTS dwd_agri_tbs_transport_daily (
    id                    SERIAL           PRIMARY KEY,
    batch_id              INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no              VARCHAR(40)      NOT NULL DEFAULT '',
    file_id               INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id      INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date           DATE             NOT NULL,
    site                  VARCHAR(120)     NOT NULL DEFAULT '',
    spb_no                VARCHAR(80)      NOT NULL DEFAULT '',
    destination_factory   VARCHAR(120)     NOT NULL DEFAULT '',
    trip_no               VARCHAR(40)      NOT NULL DEFAULT '',
    driver_name           VARCHAR(120)     NOT NULL DEFAULT '',
    license_plate         VARCHAR(40)      NOT NULL DEFAULT '',
    vehicle_code          VARCHAR(40)      NOT NULL DEFAULT '',
    source_division       VARCHAR(80)      NOT NULL DEFAULT '',
    bunch_count           DOUBLE PRECISION,
    loose_fruit_kg        DOUBLE PRECISION,
    seal_time             VARCHAR(30)      NOT NULL DEFAULT '',
    security_depart_time  VARCHAR(30)      NOT NULL DEFAULT '',
    weighbridge_time      VARCHAR(30)      NOT NULL DEFAULT '',
    weighbridge_kg        DOUBLE PRECISION,
    remark                TEXT             NOT NULL DEFAULT '',
    quality_status        VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message       TEXT             NOT NULL DEFAULT '',
    created_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_tbs_transport UNIQUE (report_date, site, spb_no)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_tbs_transport_daily_report_date ON dwd_agri_tbs_transport_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_tbs_transport_daily_site        ON dwd_agri_tbs_transport_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_harvest_plan_daily (
    id                    SERIAL           PRIMARY KEY,
    batch_id              INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no              VARCHAR(40)      NOT NULL DEFAULT '',
    file_id               INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id      INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date           DATE             NOT NULL,
    site                  VARCHAR(120)     NOT NULL DEFAULT '',
    division              VARCHAR(80)      NOT NULL DEFAULT '',
    harvest_area_ha       DOUBLE PRECISION,
    akp_value             DOUBLE PRECISION,
    leftover_h1_kg        DOUBLE PRECISION,
    leftover_h2_kg        DOUBLE PRECISION,
    leftover_h3_kg        DOUBLE PRECISION,
    planned_harvest_kg    DOUBLE PRECISION,
    planned_trips         DOUBLE PRECISION,
    planned_delivery_time VARCHAR(30)      NOT NULL DEFAULT '',
    leftover_remark       TEXT             NOT NULL DEFAULT '',
    quality_status        VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message       TEXT             NOT NULL DEFAULT '',
    created_at            TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_harvest_plan UNIQUE (report_date, site, division)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_plan_daily_report_date ON dwd_agri_harvest_plan_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_harvest_plan_daily_site        ON dwd_agri_harvest_plan_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_rainfall_daily (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    rainfall_mm      DOUBLE PRECISION,
    mtd_rainfall_mm  DOUBLE PRECISION,
    rain_start_time  VARCHAR(20)      NOT NULL DEFAULT '',
    rain_end_time    VARCHAR(20)      NOT NULL DEFAULT '',
    duration_minutes DOUBLE PRECISION,
    remark           TEXT             NOT NULL DEFAULT '',
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_rainfall UNIQUE (report_date, site)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_rainfall_daily_report_date ON dwd_agri_rainfall_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_rainfall_daily_site        ON dwd_agri_rainfall_daily(site);

CREATE TABLE IF NOT EXISTS dwd_agri_seedling_transport_daily (
    id                 SERIAL           PRIMARY KEY,
    batch_id           INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no           VARCHAR(40)      NOT NULL DEFAULT '',
    file_id            INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id   INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date        DATE             NOT NULL,
    site               VARCHAR(120)     NOT NULL DEFAULT '',
    mris_no            VARCHAR(80)      NOT NULL DEFAULT '',
    transport_purpose  VARCHAR(120)     NOT NULL DEFAULT '',
    destination_site   VARCHAR(120)     NOT NULL DEFAULT '',
    destination_blok   VARCHAR(80)      NOT NULL DEFAULT '',
    daily_qty          DOUBLE PRECISION,
    cumulative_qty     DOUBLE PRECISION,
    quality_status     VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message    TEXT             NOT NULL DEFAULT '',
    created_at         TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agri_seedling_transport UNIQUE (report_date, site, mris_no)
);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_seedling_transport_daily_report_date ON dwd_agri_seedling_transport_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_agri_seedling_transport_daily_site        ON dwd_agri_seedling_transport_daily(site);

-- ════════════════════════════════════════════════════════════
-- DWD 工厂层
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS dwd_factory_grading_daily (
    id                       SERIAL           PRIMARY KEY,
    batch_id                 INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                 VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                  INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id         INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date              DATE             NOT NULL,
    site                     VARCHAR(120)     NOT NULL DEFAULT '',
    spb_no                   VARCHAR(80)      NOT NULL DEFAULT '',
    source_company           VARCHAR(80)      NOT NULL DEFAULT '',
    source_estate_division   VARCHAR(80)      NOT NULL DEFAULT '',
    vehicle                  VARCHAR(40)      NOT NULL DEFAULT '',
    blok                     VARCHAR(80)      NOT NULL DEFAULT '',
    bunch_count              DOUBLE PRECISION,
    unripe_count             DOUBLE PRECISION,
    under_ripe_count         DOUBLE PRECISION,
    ripe_count               DOUBLE PRECISION,
    over_ripe_count          DOUBLE PRECISION,
    empty_bunch_count        DOUBLE PRECISION,
    parthenocarpic_count     DOUBLE PRECISION,
    dura_count               DOUBLE PRECISION,
    long_stalk_count         DOUBLE PRECISION,
    small_fruit_count        DOUBLE PRECISION,
    rotten_count             DOUBLE PRECISION,
    brondolan_kg             DOUBLE PRECISION,
    weight_before_grading_ton DOUBLE PRECISION,
    weight_after_grading_ton  DOUBLE PRECISION,
    rejected_kg              DOUBLE PRECISION,
    quality_status           VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message          TEXT             NOT NULL DEFAULT '',
    created_at               TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_grading UNIQUE (report_date, site, spb_no)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_grading_daily_report_date ON dwd_factory_grading_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_grading_daily_site        ON dwd_factory_grading_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_weighbridge_daily (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    ticket_no        VARCHAR(80)      NOT NULL DEFAULT '',
    direction        VARCHAR(10)      NOT NULL DEFAULT '',
    transaction_type VARCHAR(40)      NOT NULL DEFAULT '',
    product          VARCHAR(80)      NOT NULL DEFAULT '',
    vehicle          VARCHAR(40)      NOT NULL DEFAULT '',
    customer         VARCHAR(120)     NOT NULL DEFAULT '',
    transporter      VARCHAR(120)     NOT NULL DEFAULT '',
    gross_weight_kg  DOUBLE PRECISION,
    tare_weight_kg   DOUBLE PRECISION,
    netto_kg         DOUBLE PRECISION,
    bunch_count      DOUBLE PRECISION,
    loose_fruit_kg   DOUBLE PRECISION,
    bjr_kg           DOUBLE PRECISION,
    out_items        VARCHAR(200)     NOT NULL DEFAULT '',
    remark           TEXT             NOT NULL DEFAULT '',
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_weighbridge UNIQUE (report_date, site, ticket_no)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_weighbridge_daily_report_date ON dwd_factory_weighbridge_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_weighbridge_daily_site        ON dwd_factory_weighbridge_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_pom_production_daily (
    id                       SERIAL           PRIMARY KEY,
    batch_id                 INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                 VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                  INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id         INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date              DATE             NOT NULL,
    site                     VARCHAR(120)     NOT NULL DEFAULT '',
    period_type              VARCHAR(20)      NOT NULL DEFAULT 'today',
    responsible_person       VARCHAR(120)     NOT NULL DEFAULT '',
    own_ffb_before_kg        DOUBLE PRECISION,
    own_ffb_after_kg         DOUBLE PRECISION,
    plasma_ffb_before_kg     DOUBLE PRECISION,
    plasma_ffb_after_kg      DOUBLE PRECISION,
    group_ffb_before_kg      DOUBLE PRECISION,
    group_ffb_after_kg       DOUBLE PRECISION,
    external_ffb_before_kg   DOUBLE PRECISION,
    external_ffb_after_kg    DOUBLE PRECISION,
    ffb_processed_before_kg  DOUBLE PRECISION,
    ffb_processed_after_kg   DOUBLE PRECISION,
    ffb_balance_kg           DOUBLE PRECISION,
    cpo_production_kg        DOUBLE PRECISION,
    cpo_ffa_pct              DOUBLE PRECISION,
    cpo_moisture_pct         DOUBLE PRECISION,
    cpo_impurity_pct         DOUBLE PRECISION,
    pao_blend_kg             DOUBLE PRECISION,
    pao_production_kg        DOUBLE PRECISION,
    kernel_production_kg     DOUBLE PRECISION,
    kernel_moisture_pct      DOUBLE PRECISION,
    kernel_impurity_pct      DOUBLE PRECISION,
    shell_production_kg      DOUBLE PRECISION,
    cpo_sales_kg             DOUBLE PRECISION,
    miko_sales_kg            DOUBLE PRECISION,
    kernel_sales_kg          DOUBLE PRECISION,
    processing_hours         DOUBLE PRECISION,
    downtime_hours           DOUBLE PRECISION,
    downtime_reason          TEXT             NOT NULL DEFAULT '',
    remark                   TEXT             NOT NULL DEFAULT '',
    quality_status           VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message          TEXT             NOT NULL DEFAULT '',
    created_at               TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_pom_production UNIQUE (report_date, site, period_type)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_pom_production_daily_report_date ON dwd_factory_pom_production_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_pom_production_daily_site        ON dwd_factory_pom_production_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_kcp_production_daily (
    id                      SERIAL           PRIMARY KEY,
    batch_id                INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                 INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id        INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date             DATE             NOT NULL,
    site                    VARCHAR(120)     NOT NULL DEFAULT '',
    period_type             VARCHAR(20)      NOT NULL DEFAULT 'today',
    responsible_person      VARCHAR(120)     NOT NULL DEFAULT '',
    own_pk_before_kg        DOUBLE PRECISION,
    own_pk_after_kg         DOUBLE PRECISION,
    group_pk_before_kg      DOUBLE PRECISION,
    group_pk_after_kg       DOUBLE PRECISION,
    external_pk_before_kg   DOUBLE PRECISION,
    external_pk_after_kg    DOUBLE PRECISION,
    pk_processed_before_kg  DOUBLE PRECISION,
    pk_processed_after_kg   DOUBLE PRECISION,
    pk_balance_kg           DOUBLE PRECISION,
    pko_production_kg       DOUBLE PRECISION,
    pko_ffa_pct             DOUBLE PRECISION,
    pko_moisture_pct        DOUBLE PRECISION,
    pko_impurity_pct        DOUBLE PRECISION,
    line1_oil_loss_kg       DOUBLE PRECISION,
    line2_oil_loss_kg       DOUBLE PRECISION,
    pke_production_kg       DOUBLE PRECISION,
    pke_bags                DOUBLE PRECISION,
    external_crude_meal_kg  DOUBLE PRECISION,
    pko_sales_kg            DOUBLE PRECISION,
    pke_sales_kg            DOUBLE PRECISION,
    processing_hours        DOUBLE PRECISION,
    downtime_hours          DOUBLE PRECISION,
    downtime_reason         TEXT             NOT NULL DEFAULT '',
    remark                  TEXT             NOT NULL DEFAULT '',
    quality_status          VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message         TEXT             NOT NULL DEFAULT '',
    created_at              TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_kcp_production UNIQUE (report_date, site, period_type)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_kcp_production_daily_report_date ON dwd_factory_kcp_production_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_kcp_production_daily_site        ON dwd_factory_kcp_production_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_refinery_production_daily (
    id                      SERIAL           PRIMARY KEY,
    batch_id                INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no                VARCHAR(40)      NOT NULL DEFAULT '',
    file_id                 INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id        INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date             DATE             NOT NULL,
    site                    VARCHAR(120)     NOT NULL DEFAULT '',
    period_type             VARCHAR(20)      NOT NULL DEFAULT 'today',
    responsible_person      VARCHAR(120)     NOT NULL DEFAULT '',
    cpo_low_acid_input_kg   DOUBLE PRECISION,
    cpo_high_acid_input_kg  DOUBLE PRECISION,
    cpko_input_kg           DOUBLE PRECISION,
    olein_input_kg          DOUBLE PRECISION,
    stearin_input_kg        DOUBLE PRECISION,
    rbdpo_input_kg          DOUBLE PRECISION,
    rbdst_tank_input_kg     DOUBLE PRECISION,
    rbdpol_tank_input_kg    DOUBLE PRECISION,
    total_input_kg          DOUBLE PRECISION,
    rbdpo_production_kg     DOUBLE PRECISION,
    rbdpko_production_kg    DOUBLE PRECISION,
    pfad_production_kg      DOUBLE PRECISION,
    pkfad_production_kg     DOUBLE PRECISION,
    rbdol_production_kg     DOUBLE PRECISION,
    rbdst_production_kg     DOUBLE PRECISION,
    oilku_1l_production_kg  DOUBLE PRECISION,
    oilku_2l_production_kg  DOUBLE PRECISION,
    total_production_kg     DOUBLE PRECISION,
    unit_processing_cost    DOUBLE PRECISION,
    rbdpo_sales_kg          DOUBLE PRECISION,
    rbdpo_sales_pu_kg       DOUBLE PRECISION,
    rbdpo_sales_asp_kg      DOUBLE PRECISION,
    rbdpko_sales_kg         DOUBLE PRECISION,
    pfad_sales_kg           DOUBLE PRECISION,
    pkfad_sales_kg          DOUBLE PRECISION,
    rbdol_sales_kg          DOUBLE PRECISION,
    rbdst_sales_kg          DOUBLE PRECISION,
    oilku_1l_sales_kg       DOUBLE PRECISION,
    oilku_2l_sales_kg       DOUBLE PRECISION,
    total_sales_kg          DOUBLE PRECISION,
    remark                  TEXT             NOT NULL DEFAULT '',
    quality_status          VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message         TEXT             NOT NULL DEFAULT '',
    created_at              TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_refinery_production UNIQUE (report_date, site, period_type)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_refinery_production_daily_report_date ON dwd_factory_refinery_production_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_refinery_production_daily_site        ON dwd_factory_refinery_production_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_product_inventory_daily (
    id                   SERIAL           PRIMARY KEY,
    batch_id             INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no             VARCHAR(40)      NOT NULL DEFAULT '',
    file_id              INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id     INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date          DATE             NOT NULL,
    site                 VARCHAR(120)     NOT NULL DEFAULT '',
    product_type         VARCHAR(40)      NOT NULL DEFAULT '',
    product_spec         VARCHAR(80)      NOT NULL DEFAULT '',
    storage_location     VARCHAR(80)      NOT NULL DEFAULT '',
    tank_no              VARCHAR(40)      NOT NULL DEFAULT '',
    capacity             DOUBLE PRECISION,
    actual_stock         DOUBLE PRECISION,
    unit                 VARCHAR(20)      NOT NULL DEFAULT '',
    ffa_pct              DOUBLE PRECISION,
    moisture_pct         DOUBLE PRECISION,
    impurity_pct         DOUBLE PRECISION,
    eom_forecast_stock   DOUBLE PRECISION,
    remark               TEXT             NOT NULL DEFAULT '',
    quality_status       VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message      TEXT             NOT NULL DEFAULT '',
    created_at           TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_product_inv UNIQUE (report_date, site, product_type, product_spec, tank_no)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_product_inventory_daily_report_date ON dwd_factory_product_inventory_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_product_inventory_daily_site        ON dwd_factory_product_inventory_daily(site);

CREATE TABLE IF NOT EXISTS dwd_factory_chemical_consumption_daily (
    id               SERIAL           PRIMARY KEY,
    batch_id         INTEGER          REFERENCES upload_batches(id) ON DELETE SET NULL,
    batch_no         VARCHAR(40)      NOT NULL DEFAULT '',
    file_id          INTEGER          REFERENCES upload_files(id) ON DELETE SET NULL,
    source_record_id INTEGER          REFERENCES parsed_structured_records(id) ON DELETE SET NULL,
    report_date      DATE             NOT NULL,
    site             VARCHAR(120)     NOT NULL DEFAULT '',
    chemical_code    VARCHAR(60)      NOT NULL DEFAULT '',
    chemical_name    VARCHAR(120)     NOT NULL DEFAULT '',
    unit             VARCHAR(20)      NOT NULL DEFAULT 'kg',
    consumption_qty  DOUBLE PRECISION,
    quality_status   VARCHAR(40)      NOT NULL DEFAULT 'ok',
    quality_message  TEXT             NOT NULL DEFAULT '',
    created_at       TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_factory_chemical UNIQUE (report_date, site, chemical_code)
);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_chemical_consumption_daily_report_date ON dwd_factory_chemical_consumption_daily(report_date);
CREATE INDEX IF NOT EXISTS ix_dwd_factory_chemical_consumption_daily_site        ON dwd_factory_chemical_consumption_daily(site);

-- ════════════════════════════════════════════════════════════
-- 经营指数体系
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS index_definitions (
    id          SERIAL       PRIMARY KEY,
    code        VARCHAR(40)  NOT NULL,
    name        VARCHAR(120) NOT NULL,
    formula     TEXT         NOT NULL DEFAULT '',
    description TEXT         NOT NULL DEFAULT '',
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    granularity VARCHAR(20)  NOT NULL DEFAULT 'monthly',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_index_definitions_code UNIQUE (code)
);
CREATE INDEX IF NOT EXISTS ix_index_definitions_code ON index_definitions(code);

CREATE TABLE IF NOT EXISTS index_sub_metrics (
    id                  SERIAL           PRIMARY KEY,
    index_id            INTEGER          NOT NULL REFERENCES index_definitions(id) ON DELETE CASCADE,
    code                VARCHAR(40)      NOT NULL,
    name                VARCHAR(120)     NOT NULL DEFAULT '',
    unit                VARCHAR(40)      NOT NULL DEFAULT '',
    source_type         VARCHAR(20)      NOT NULL DEFAULT 'manual',
    fixed_value         DOUBLE PRECISION,
    db_table            VARCHAR(120),
    db_field            VARCHAR(120),
    db_aggregation      VARCHAR(20)      NOT NULL DEFAULT 'SUM',
    db_date_col         VARCHAR(120)     NOT NULL DEFAULT 'report_date',
    db_extra_where      TEXT,
    fiscal_start_month  INTEGER,
    sort_order          INTEGER          NOT NULL DEFAULT 0,
    created_at          TIMESTAMP        NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_index_sub_metrics_index_id ON index_sub_metrics(index_id);

CREATE TABLE IF NOT EXISTS index_data_entries (
    id             SERIAL           PRIMARY KEY,
    sub_metric_id  INTEGER          NOT NULL REFERENCES index_sub_metrics(id) ON DELETE CASCADE,
    period_year    INTEGER          NOT NULL,
    period_month   INTEGER          NOT NULL,
    value          DOUBLE PRECISION,
    source         VARCHAR(40)      NOT NULL DEFAULT 'manual',
    remark         TEXT             NOT NULL DEFAULT '',
    created_by     VARCHAR(120)     NOT NULL DEFAULT '',
    created_at     TIMESTAMP        NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_index_data_entry UNIQUE (sub_metric_id, period_year, period_month)
);
CREATE INDEX IF NOT EXISTS ix_index_data_entries_sub_metric_id ON index_data_entries(sub_metric_id);
CREATE INDEX IF NOT EXISTS ix_index_data_entries_period_year   ON index_data_entries(period_year);
CREATE INDEX IF NOT EXISTS ix_index_data_entries_period_month  ON index_data_entries(period_month);

CREATE TABLE IF NOT EXISTS system_configs (
    key        VARCHAR(120) PRIMARY KEY,
    value      TEXT         NOT NULL DEFAULT '',
    updated_by VARCHAR(120) NOT NULL DEFAULT '',
    updated_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduled_syncs (
    id            SERIAL       PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    sync_type     VARCHAR(40)  NOT NULL,
    sub_metric_id INTEGER,
    months        INTEGER      NOT NULL DEFAULT 12,
    cron_minute   VARCHAR(20)  NOT NULL DEFAULT '0',
    cron_hour     VARCHAR(20)  NOT NULL DEFAULT '2',
    cron_day      VARCHAR(20)  NOT NULL DEFAULT '*',
    cron_month    VARCHAR(20)  NOT NULL DEFAULT '*',
    cron_dow      VARCHAR(20)  NOT NULL DEFAULT '*',
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_run_at   TIMESTAMP,
    last_status   VARCHAR(20),
    last_message  TEXT,
    created_by    VARCHAR(120) NOT NULL DEFAULT '',
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- 主数据 INSERT
-- 密码说明：admin 初始密码为 admin123（bcrypt hash）
-- ════════════════════════════════════════════════════════════

INSERT INTO users (id, username, password_hash, display_name, role, department, site, is_active, created_at, updated_at)
VALUES (1, 'admin', '$2b$12$0LPC3m7L.ElLVrSnv9QaruNEft26TxJiRFm9KX2GziKYkDOoPtZLe', '管理员', 'admin', 'IT&Bigdata', 'HO', TRUE, NOW(), NOW())
ON CONFLICT (username) DO NOTHING;

INSERT INTO system_configs (key, value, updated_by, updated_at) VALUES
    ('composite_index_formula', '',        'admin', NOW()),
    ('composite_index_label',   '综合指数', 'admin', NOW()),
    ('teams_notify_on',         'success', 'admin', NOW()),
    ('teams_webhook_url',       '',        'admin', NOW())
ON CONFLICT (key) DO NOTHING;

INSERT INTO index_definitions (id, code, name, formula, description, sort_order, is_active, granularity, created_at, updated_at)
VALUES (3, 'agri', '农业', 'production_bg/1000/budget * 100 + 100', '', 0, TRUE, 'daily', NOW(), NOW())
ON CONFLICT (code) DO NOTHING;

INSERT INTO index_sub_metrics (id, index_id, code, name, unit, sort_order, source_type, db_table, db_field, db_aggregation, db_date_col, db_extra_where, fiscal_start_month, fixed_value, created_at)
VALUES
    (3, 3, 'production_bg', '产量年累计', 'kg',  0, 'db_sync', 'dwd.sap_harvest_actual_block_daily', 'production_bg', 'SUM', 'date',        NULL, 9,    NULL,       NOW()),
    (4, 3, 'budget',        '产量预算',   '吨',  1, 'fixed',   NULL,                                  NULL,            'SUM', 'report_date', NULL, NULL, 1122005.0, NOW())
ON CONFLICT DO NOTHING;

-- 农业产量累计数据（sub_metric_id=3, production_bg, 单位 kg）
INSERT INTO index_data_entries (id, sub_metric_id, period_year, period_month, value, source, remark, created_by, created_at, updated_at)
VALUES
    (1,  3, 2025, 7,  951544089.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (2,  3, 2025, 8,  1043018287.0, 'db_sync', '', 'admin', NOW(), NOW()),
    (3,  3, 2025, 9,  92275257.0,   'db_sync', '', 'admin', NOW(), NOW()),
    (4,  3, 2025, 10, 189705693.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (5,  3, 2025, 11, 283866547.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (6,  3, 2025, 12, 367546467.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (7,  3, 2026, 1,  446173473.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (8,  3, 2026, 2,  520342923.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (9,  3, 2026, 3,  597245221.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (10, 3, 2026, 4,  690959909.5,  'db_sync', '', 'admin', NOW(), NOW()),
    (11, 3, 2026, 5,  796943675.5,  'db_sync', '', 'admin', NOW(), NOW()),
    (12, 3, 2026, 6,  NULL,         'db_sync', '', 'admin', NOW(), NOW()),
    (13, 3, 2024, 9,  89959780.0,   'db_sync', '', 'admin', NOW(), NOW()),
    (14, 3, 2024, 10, 179001200.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (15, 3, 2024, 11, 261158389.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (16, 3, 2024, 12, 340670904.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (17, 3, 2025, 1,  421583076.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (18, 3, 2025, 2,  496632154.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (19, 3, 2025, 3,  572717846.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (20, 3, 2025, 4,  658569923.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (21, 3, 2025, 5,  741995104.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (22, 3, 2025, 6,  816094233.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (23, 3, 2024, 1,  73934131.0,   'db_sync', '', 'admin', NOW(), NOW()),
    (24, 3, 2024, 2,  127732690.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (25, 3, 2024, 3,  180906113.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (26, 3, 2024, 4,  240299543.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (27, 3, 2024, 5,  307467722.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (28, 3, 2024, 6,  365818016.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (29, 3, 2024, 7,  424768705.0,  'db_sync', '', 'admin', NOW(), NOW()),
    (30, 3, 2024, 8,  504178052.0,  'db_sync', '', 'admin', NOW(), NOW())
ON CONFLICT DO NOTHING;

INSERT INTO scheduled_syncs (id, name, sync_type, sub_metric_id, months, cron_minute, cron_hour, cron_day, cron_month, cron_dow, enabled, created_by, created_at, updated_at)
VALUES (1, '农业产量每日同步', 'agri_production', 3, 2, '0', '14', '*', '*', '*', TRUE, 'admin', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- 重置序列，避免后续 INSERT 冲突
SELECT setval('users_id_seq',              COALESCE((SELECT MAX(id) FROM users), 1),              true);
SELECT setval('index_definitions_id_seq',  COALESCE((SELECT MAX(id) FROM index_definitions), 1),  true);
SELECT setval('index_sub_metrics_id_seq',  COALESCE((SELECT MAX(id) FROM index_sub_metrics), 1),  true);
SELECT setval('index_data_entries_id_seq', COALESCE((SELECT MAX(id) FROM index_data_entries), 1), true);
SELECT setval('scheduled_syncs_id_seq',    COALESCE((SELECT MAX(id) FROM scheduled_syncs), 1),    true);

COMMIT;

-- ============================================================
-- 初始化完成
-- 登录账号：admin / admin123（请登录后立即修改密码）
-- ============================================================
