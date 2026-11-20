from sqlalchemy import (
    Boolean, CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, Integer, MetaData,
    String, Table, Text, UniqueConstraint,
)

metadata = MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})

departments = Table("department", metadata, Column("id", Integer, primary_key=True),
                    Column("name", String(80), nullable=False, unique=True))
users = Table("user", metadata, Column("id", Integer, primary_key=True),
              Column("username", String(32), nullable=False, unique=True),
              Column("name", String(80), nullable=False),
              Column("password_hash", String(255), nullable=False),
              Column("department_id", ForeignKey("department.id"), nullable=False),
              Column("active", Boolean, nullable=False))
roles = Table("role", metadata, Column("id", Integer, primary_key=True),
              Column("code", String(32), nullable=False, unique=True),
              Column("name", String(80), nullable=False))
permissions = Table("permission", metadata, Column("code", String(48), primary_key=True))
user_roles = Table("user_role", metadata,
                   Column("user_id", ForeignKey("user.id"), primary_key=True),
                   Column("role_id", ForeignKey("role.id"), primary_key=True))
role_permissions = Table("role_permission", metadata,
                         Column("role_id", ForeignKey("role.id"), primary_key=True),
                         Column("permission_code", ForeignKey("permission.code"), primary_key=True),
                         Column("scope", String(10), nullable=False),
                         CheckConstraint("scope IN ('own','department','all')", name="scope"))
datasets = Table("dataset", metadata, Column("id", Integer, primary_key=True),
                 Column("code", String(32), nullable=False, unique=True),
                 Column("name", String(80), nullable=False),
                 Column("description", Text, nullable=False))
metrics = Table("metric", metadata, Column("id", Integer, primary_key=True),
                Column("dataset_id", ForeignKey("dataset.id"), nullable=False),
                Column("code", String(32), nullable=False),
                Column("name", String(80), nullable=False),
                Column("unit", String(12), nullable=False),
                Column("description", Text, nullable=False),
                UniqueConstraint("dataset_id", "code"))
dimensions = Table("dimension", metadata, Column("id", Integer, primary_key=True),
                    Column("dataset_id", ForeignKey("dataset.id"), nullable=False),
                    Column("code", String(32), nullable=False),
                    Column("name", String(80), nullable=False),
                    Column("description", Text, nullable=False),
                    UniqueConstraint("dataset_id", "code"))
sales = Table("sales_fact", metadata, Column("id", Integer, primary_key=True),
              Column("dataset_id", ForeignKey("dataset.id"), nullable=False),
              Column("owner_id", ForeignKey("user.id"), nullable=False),
              Column("department_id", ForeignKey("department.id"), nullable=False),
              Column("day", String(10), nullable=False),
              Column("channel", String(30), nullable=False),
              Column("product", String(40), nullable=False),
              Column("revenue", Integer, nullable=False),
              Column("orders", Integer, nullable=False),
              Column("refunds", Integer, nullable=False))
Index("ix_sales_dataset_day", sales.c.dataset_id, sales.c.day)

query_logs = Table("query_log", metadata, Column("id", Integer, primary_key=True),
                   Column("user_id", ForeignKey("user.id"), nullable=False),
                   Column("department_id", ForeignKey("department.id"), nullable=False),
                   Column("dataset_id", ForeignKey("dataset.id"), nullable=False),
                   Column("metric", String(32), nullable=False),
                   Column("dimension", String(32), nullable=False),
                   Column("scope", String(10), nullable=False),
                   Column("filters_json", Text, nullable=False),
                   Column("status", String(16), nullable=False),
                   Column("elapsed_ms", Integer, nullable=False),
                   Column("row_count", Integer, nullable=False),
                   Column("result_json", Text),
                   Column("created_at", String(32), nullable=False))
Index("ix_query_created_id", query_logs.c.created_at, query_logs.c.id)
Index("ix_query_user_created_id", query_logs.c.user_id, query_logs.c.created_at, query_logs.c.id)
Index("ix_query_department_created_id", query_logs.c.department_id, query_logs.c.created_at, query_logs.c.id)

reports = Table("report", metadata, Column("id", Integer, primary_key=True, autoincrement="ignore_fk"),
                Column("owner_id", ForeignKey("user.id"), nullable=False),
                Column("department_id", ForeignKey("department.id"), nullable=False),
                Column("dataset_id", ForeignKey("dataset.id")),
                Column("title", String(120), nullable=False),
                Column("description", String(500), nullable=False),
                Column("content", Text, nullable=False),
                Column("query_id", ForeignKey("query_log.id")),
                Column("status", String(12), nullable=False),
                Column("current_version", Integer),
                Column("created_at", String(32), nullable=False),
                Column("updated_at", String(32), nullable=False),
                Column("deleted_at", String(32)),
                CheckConstraint("status IN ('draft','published','archived')", name="status"),
                ForeignKeyConstraint(["id", "current_version"], ["report_version.report_id", "report_version.number"],
                                     name="fk_report_current_version", use_alter=True))
live = reports.c.deleted_at.is_(None)
Index("ix_report_live_updated_id", reports.c.updated_at, reports.c.id, sqlite_where=live)
Index("ix_report_live_status_updated_id", reports.c.status, reports.c.updated_at, reports.c.id, sqlite_where=live)
Index("ix_report_live_owner_updated_id", reports.c.owner_id, reports.c.updated_at, reports.c.id, sqlite_where=live)
Index("ix_report_live_department_updated_id", reports.c.department_id, reports.c.updated_at, reports.c.id, sqlite_where=live)

versions = Table("report_version", metadata,
                 Column("report_id", ForeignKey("report.id"), primary_key=True),
                 Column("number", Integer, primary_key=True),
                 Column("created_by", ForeignKey("user.id"), nullable=False),
                 Column("created_at", String(32), nullable=False),
                 Column("restored_from", Integer),
                 Column("snapshot_json", Text, nullable=False),
                 ForeignKeyConstraint(["report_id", "restored_from"], ["report_version.report_id", "report_version.number"]))
assets = Table("asset", metadata, Column("id", Integer, primary_key=True),
               Column("owner_id", ForeignKey("user.id"), nullable=False),
               Column("storage_key", String(48), nullable=False, unique=True),
               Column("filename", String(200), nullable=False),
               Column("mime", String(64), nullable=False),
               Column("size_bytes", Integer, nullable=False),
               Column("created_at", String(32), nullable=False))
report_assets = Table("report_asset", metadata,
                      Column("report_id", ForeignKey("report.id"), primary_key=True),
                      Column("asset_id", ForeignKey("asset.id"), primary_key=True))
version_assets = Table("version_asset", metadata,
                       Column("report_id", Integer, primary_key=True),
                       Column("version", Integer, primary_key=True),
                       Column("asset_id", ForeignKey("asset.id"), primary_key=True),
                       ForeignKeyConstraint(["report_id", "version"], ["report_version.report_id", "report_version.number"]))
audit_logs = Table("audit_log", metadata, Column("id", Integer, primary_key=True),
                   Column("user_id", ForeignKey("user.id"), nullable=False),
                   Column("action", String(48), nullable=False),
                   Column("resource", String(32), nullable=False),
                   Column("resource_id", Integer),
                   Column("detail_json", Text, nullable=False),
                   Column("created_at", String(32), nullable=False))
Index("ix_audit_created_id", audit_logs.c.created_at, audit_logs.c.id)
