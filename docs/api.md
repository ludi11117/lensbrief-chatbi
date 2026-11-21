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
| `GET /reports/summary` | 当前权限下的报告总数及各状态计数 | report.read |
| `POST /reports` | 创建草稿，返回报告，HTTP 201 | report.create |
| `GET /reports/{id}` | 报告内容、附件、状态、当前版本与动作授权 | report.read |
| `PUT /reports/{id}` | 替换工作稿字段和附件清单 | report.edit |
| `DELETE /reports/{id}` | 软删除，HTTP 204 | report.delete |
| `POST /reports/{id}/publish` | 发布当前工作稿，新建版本，HTTP 201 | report.publish |
| `POST /reports/{id}/archive` | 归档已发布的报告 | report.archive |
| `GET /reports/{id}/versions` | 版本历史分页，按版本号倒序 | report.read |
| `GET /reports/{id}/versions/{number}` | 查看不可修改的版本快照 | report.read |
| `GET /reports/{id}/versions/diff?base=1&target=2` | 比较元数据和正文逐行变更 | report.read |
| `GET /reports/{id}/versions/{number}/feedback` | 指定版本的反馈，按最新发布顺序分页 | report.read |
| `POST /reports/{id}/versions/{number}/feedback` | 提交 `{"body":"建议核对渠道归类"}`，HTTP 201 | report.read，报告处于已发布状态 |
| `POST /reports/{id}/rollback/{number}` | 用历史版本新建一个发布版本，HTTP 201 | report.rollback |
| `GET /datasets` | 数据集目录分页 | dataset.read |
| `GET /datasets/{id}/metrics` | 指标编码、名称、单位与口径分页 | dataset.read |
| `GET /datasets/{id}/dimensions` | 维度编码、名称与口径分页 | dataset.read |
| `POST /queries/plan` | 将提问解析成可确认的指标、维度、日期和范围 | dataset.query，上下文限本人 |
| `POST /queries` | 执行聚合并写查询日志，返回查询 ID 和结果，HTTP 201 | dataset.query |
| `GET /queries` | 查询日志分页，支持 `user_id`、`context_id`、`start`、`end` | query.read，上下文筛选限本人 |
| `GET /queries/{id}` | 查询条件及结果，适用当前有效数据范围。上下文 ID 仅向执行者返回 | query.read |
| `POST /drafts/generate` | 按已有聚合生成草稿，返回草稿字段和模式 | report.create、query.read |
| `GET /knowledge/packs` | 知识包分页，可按 `dataset_id` 筛选 | dataset.read |
| `GET /knowledge/packs/{id}` | 查看当前知识包版本与条目 | dataset.read |
| `POST /knowledge/packs` | 创建知识包，HTTP 201 | knowledge.manage |
| `PUT /knowledge/packs/{id}` | 修改知识包和条目，递增版本 | knowledge.manage |
| `GET /contexts` | 本人的上下文分页，可按 `dataset_id`、`archived` 筛选 | dataset.query |
| `POST /contexts` | 新建个人上下文，HTTP 201 | dataset.query |
| `GET /contexts/{id}` | 查看个人上下文 | 所有者、dataset.query |
| `PUT /contexts/{id}` | 更新目标与知识包，归档或恢复 | 所有者、dataset.query |
| `GET /assets` | 分页列出本人上传的文件，最近上传优先，可用 `limit` 和 `offset` | asset.upload |
| `POST /assets` | 上传，字段名 `file`，单文件 5 MiB，HTTP 201 | asset.upload |
| `GET /assets/{id}/content` | 读取文件，可传 `report_id`、`version`、`download=true` | 所有者或关联报告权限 |
| `GET /assets/{id}/csv` | CSV 表头、前 100 行与总行数，可传 `report_id` 与 `version` | 所有者或关联报告权限 |
| `GET /access` | 查看用户、角色与权限范围 | user.manage |
| `PUT /access/users/{id}/roles` | 替换目标用户角色，接收 `{"roles":["analyst"]}` | user.manage |
| `GET /audit` | 操作审计分页，可用 `action=access.denied` 按动作筛选 | audit.read |

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

对渠道、产品或部门分组可发送 `compare_previous: true`。服务端使用当前范围前方紧邻的等长区间，在相同权限和指标口径下汇总，并返回 `comparison` 内的 `start`、`end`、`rows`。未勾选对照时该字段为 `null`。查询日志的 `row_count` 仍为本期行数，报告快照会保存两期。

`GET /datasets/{id}/dimensions` 的 `channel` 维度可返回 `values`。维度目录和问题解析可传入 `scope=own` 或 `department`，并按该范围返回可用渠道。查询可传其中一个值到可选的 `channel` 字段，两期对照使用相同筛选。该字段也会保存在查询结果和报告快照。

### 解析自然语言问题

`POST /queries/plan` 接受 `{"dataset_id":1,"question":"2026年10月按渠道看销售额"}`，可加 `context_id`。响应包含查询字段、解析来源 `source`（`rules` 或 `llm`）及说明数组 `notes`。界面展示解析结果，用户确认后将查询字段提交到 `POST /queries`。规划阶段只生成查询条件，查询日志从聚合执行阶段开始记录。

日期可用整月、单日或 `YYYY-MM-DD 至 YYYY-MM-DD` 区间。「最近 7 天」等表达以当前权限范围内最新数据日为末日，支持 1 到 366 天。省略日期时，普通提问选用授权范围内最近最多 30 个自然日。追问以「改按」「改看」等开头，沿用该用户在同一上下文内可用的最新成功查询。含歧义或超出规则范围的问题返回 422，归档上下文返回 409。

问题里的渠道名按当前可用渠道精确匹配，解析结果在 `channel` 返回匹配值。追问「改成全部渠道」会清除原渠道筛选。

问题包含「对照上一期」时返回 `compare_previous: true`。后续追问可沿用上一期对照，或用「改为取消对照」关闭。按日分组只查询本期，明确要求按日对照会返回 422。

开启 `LENSBRIEF_PLANNER_MODE=llm` 后，规则未匹配到的指标或维度可由模型补齐。模型输出由字段白名单、数据集目录和已解析条件校验。配置缺失且需要模型时返回 503，模型超时或输出校验失败返回 502。

### 草稿、发布与比较

`POST /drafts/generate` 接收 `{"query_id":7,"goal":"复盘十月渠道销售"}`。可添加 `"mode":"mock"` 直接使用离线草稿。两种模式使用相同的报告和查询权限。将返回的标题、摘要和正文保存到 `POST /reports` 或 `PUT /reports/{id}`：

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

`query_id` 必须为同数据集的成功查询。新附件须由当前用户上传。表单保存后可发起发布，无需请求体。发布和回滚在同一个数据库事务中更新版本、报告指针与审计。归档是终止状态，编辑、发布或回滚会返回 409。归档报告和只能读取的已发布报告以当前发布版本的标题与摘要为准，列表搜索使用同一口径。

报告详情的响应头 `ETag` 与响应体 `etag` 表示读取时的工作稿。调用 `PUT /reports/{id}` 或 `POST /reports/{id}/publish` 时可将其原样放入 `If-Match`。服务端在写事务内核对条件。工作稿已变更时返回 412，调用方应读取最新内容后重新提交。

`diff` 返回 `{base,target,changes,content_changed,content_diff}`。元数据条目包含 `field`、`before`、`after`，涉及标题、摘要、数据集、查询和附件 ID。`content_diff` 是 unified diff 文本行数组，包含新增、删除与相邻的上下文行。

反馈绑定报告和版本号，包含 `id`、`author_name`、`body`、`created_at`。正文为 1 至 1200 字符。归档后可以查看反馈，提交新反馈返回 409。报告页面用 `?version=1` 链接定位到指定版本。

### 场景知识与上下文

`POST /knowledge/packs` 接受 `dataset_id`、`title`、`description` 与 `items`。条目包含 `title`、`content` 与可选 `metric_id`。空指标表示该条目适用于包内所有指标，最多保存 8 条。

`POST /contexts` 示例：

```json
{
  "dataset_id": 1,
  "knowledge_pack_id": 1,
  "title": "渠道周会",
  "objective": "检查不同渠道的销售额口径",
  "archived": false
}
```

在 `POST /queries` 提供可选 `context_id`，查询使用该上下文选用的知识包。上下文和知识包须与查询同属一个数据集。有效引用存入响应的 `knowledge` 字段和查询快照，包含 `id`、`title`、`revision` 与 `items`。调用方可用 `GET /queries?context_id=<id>` 查看该上下文的历史。归档上下文继续保留历史，发起新查询返回 409。

### 文件权限

不传 `report_id` 时仅上传者可以读取。传入报告 ID 且省略版本时，工作稿附件要求编辑权限。已归档报告从当前发布版本读取附件。指定 `version` 时，文件须存在于该版本的快照，调用者须能读取报告。

### 错误

| 状态码 | 触发条件 |
| --- | --- |
| 401 | 凭据错误、缺少 JWT 或 JWT 失效。 |
| 403 | 角色或数据范围不允许，记录拒绝审计。 |
| 404 | 报告已删除、资源或版本不存在、存储文件缺失。 |
| 409 | 非法状态变更，或尝试修改当前管理员自己的角色。 |
| 412 | 提交的 `If-Match` 已过期，工作稿有其他更新。 |
| 413 | 文件大小超过限制。 |
| 415 | 文件类型不支持、扩展名和内容不一致，或预览类型错误。 |
| 422 | 请求字段无效、日期不合法或查询引用不匹配。 |
| 502 | 模型接口失败或返回不符合草稿结构。 |
| 503 | 真实模型模式缺少必要配置。 |
