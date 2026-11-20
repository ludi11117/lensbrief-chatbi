# LensBrief REST API

请求以 `/api` 为前缀。Swagger 位于 `/api/docs`，OpenAPI JSON 位于 `/api/openapi.json`。除登录和健康检查外，在请求头发送 `Authorization: Bearer <token>`。应用按 JWT 主体读取当前身份与权限。

列表返回 `{items, total, limit, offset}`。所有列表分页接受 `limit=1..100`、`offset>=0`，超过尾页返回空列表和筛选后的总数。更新接口使用 JSON，文件上传使用 `multipart/form-data`。

## 接口清单

| 请求 | 行为 | 所需权限 |
| --- | --- | --- |
| `GET /health` | SQLite 与迁移后数据表可用性，返回当前草稿模式 | 公开 |
| `POST /auth/login` | 接收用户名、密码，返回 8 小时 JWT 和身份 | 公开 |
| `GET /auth/me` | 返回当前账号、角色和动作范围 | 已登录 |
| `GET /reports` | 报告分页，`status` 可取 draft、published、archived，`q` 匹配标题或摘要 | report.read |
| `POST /reports` | 创建草稿，返回报告，HTTP 201 | report.create |
| `GET /reports/{id}` | 报告内容、附件、状态、当前版本与动作授权 | report.read |
| `PUT /reports/{id}` | 替换工作稿字段和附件清单 | report.edit |
| `DELETE /reports/{id}` | 软删除，HTTP 204 | report.delete |
| `POST /reports/{id}/publish` | 发布当前工作稿，新建版本，HTTP 201 | report.publish |
| `POST /reports/{id}/archive` | 归档已发布的报告 | report.archive |
| `GET /reports/{id}/versions` | 版本历史分页，按版本号倒序 | report.read |
| `GET /reports/{id}/versions/{number}` | 查看不可修改的版本快照 | report.read |
| `GET /reports/{id}/versions/diff?base=1&target=2` | 比较元数据与正文是否变化 | report.read |
| `POST /reports/{id}/rollback/{number}` | 用历史版本新建一个发布版本，HTTP 201 | report.rollback |
| `GET /datasets` | 数据集目录分页 | dataset.read |
| `GET /datasets/{id}/metrics` | 指标编码、名称、单位与口径分页 | dataset.read |
| `GET /datasets/{id}/dimensions` | 维度编码、名称与口径分页 | dataset.read |
| `POST /queries` | 执行聚合并写查询日志，返回查询 ID 和结果，HTTP 201 | dataset.query |
| `GET /queries` | 查询日志分页，支持 `user_id`、`start`、`end` | query.read |
| `GET /queries/{id}` | 查询条件及结果，适用当前有效数据范围 | query.read |
| `POST /drafts/generate` | 按已有聚合生成草稿，返回草稿字段和模式 | report.create、query.read |
| `POST /assets` | 上传，字段名 `file`，单文件 5 MiB，HTTP 201 | asset.upload |
| `GET /assets/{id}/content` | 读取文件，可传 `report_id`、`version`、`download=true` | 所有者或关联报告权限 |
| `GET /assets/{id}/csv` | CSV 表头、前 100 行与总行数，可传 `report_id` 与 `version` | 所有者或关联报告权限 |
| `GET /access` | 查看用户、角色与权限范围 | user.manage |
| `PUT /access/users/{id}/roles` | 替换目标用户角色，接收 `{"roles":["analyst"]}` | user.manage |
| `GET /audit` | 操作审计分页 | audit.read |

### 认证和查询示例

```json
{"username":"analyst","password":"LensBrief2026!"}
```

请求 `POST /queries`：

```json
{
  "dataset_id": 1,
  "metric": "gmv",
  "dimension": "channel",
  "start": "2026-10-01",
  "end": "2026-10-31",
  "scope": "own"
}
```

`scope` 可省略，默认采用当前权限的最广数据范围。指定超出授权的范围会返回 403。查询日期包含两端，最长 366 天。查询日志的日期筛选以 UTC 日期为准，含起止日。完成的查询、范围拒绝与目录校验失败均写入日志。无法通过请求结构校验的请求，以及指向不存在数据集的请求，在执行前终止。

### 草稿、发布与比较

`POST /drafts/generate` 接收 `{"query_id":7,"goal":"复盘十月渠道销售"}`。将返回的标题、摘要和正文保存到 `POST /reports` 或 `PUT /reports/{id}`：

```json
{
  "title": "十月渠道销售复盘",
  "description": "比较各渠道成交金额",
  "content": "正文使用纯文本，可以换行。",
  "dataset_id": 1,
  "query_id": 7,
  "asset_ids": [1]
}
```

`query_id` 必须为同数据集的成功查询。新附件须由当前用户上传。表单保存后可发起发布，无需请求体。发布和回滚在同一个数据库事务中更新版本、报告指针与审计。归档是终止状态，编辑、发布或回滚会返回 409。

`diff` 返回 `{base,target,changes,content_changed}`。变更条目包含 `field`、`before`、`after`，涉及标题、摘要、数据集、查询和附件 ID。

### 文件权限

不传 `report_id` 时仅上传者可以读取。传入报告 ID 且省略版本时，工作稿附件要求编辑权限。已归档报告从当前发布版本读取附件。指定 `version` 时，文件须存在于该版本的快照，调用者须能读取报告。

### 错误

| 状态码 | 触发条件 |
| --- | --- |
| 401 | 凭据错误、缺少 JWT 或 JWT 失效。 |
| 403 | 角色或数据范围不允许，记录拒绝审计。 |
| 404 | 报告已删除、资源或版本不存在、存储文件缺失。 |
| 409 | 非法状态变更，或尝试修改当前管理员自己的角色。 |
| 413 | 文件大小超过限制。 |
| 415 | 文件类型不支持、扩展名和内容不一致，或预览类型错误。 |
| 422 | 请求字段无效、日期不合法或查询引用不匹配。 |
| 502 | 模型接口失败或返回不符合草稿结构。 |
| 503 | 真实模型模式缺少必要配置。 |
