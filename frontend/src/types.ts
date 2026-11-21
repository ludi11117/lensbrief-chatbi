export type Scope = 'own' | 'department' | 'all'
export type Status = 'draft' | 'published' | 'archived'
export interface Actor { id: number; username: string; name: string; department_id: number; roles: string[]; grants: Record<string, Scope> }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Dataset { id: number; code: string; name: string; description: string }
export interface CatalogMetric { id: number; code: string; name: string; description: string }
export interface KnowledgeItem { title: string; content: string; metric_id: number | null }
export interface KnowledgePackRow { id: number; dataset_id: number; title: string; description: string; revision: number; updated_at: string }
export interface KnowledgePack extends KnowledgePackRow { items: KnowledgeItem[] }
export interface KnowledgeSnapshot { id: number; title: string; revision: number; items: KnowledgeItem[] }
export interface AnalysisContextInput { dataset_id: number; knowledge_pack_id: number | null; title: string; objective: string; archived: boolean }
export interface AnalysisContext extends AnalysisContextInput { id: number; pack_title: string | null; updated_at: string }
export interface Asset { id: number; filename: string; mime: string; size_bytes: number }
export interface QueryResult {
  id?: number; metric_name: string; dimension_name: string; metric_note: string; unit: string;
  scope: Scope; start: string; end: string; rows: { label: string; value: number | null }[]
  knowledge?: KnowledgeSnapshot | null
}
export interface QueryPlan {
  dataset_id: number; context_id: number | null; scope: Scope
  metric: string; dimension: string; start: string; end: string; notes: string[]
  source: 'rules' | 'llm'
}
export interface ReportRow {
  id: number; title: string; description: string; status: Status; owner_id: number
  owner_name: string; current_version: number | null; updated_at: string
}
export interface Snapshot {
  title: string; description: string; content: string; dataset_id: number | null; query_id: number | null
  asset_ids: number[]; assets: Asset[]; query: QueryResult | null
}
export interface Report extends Snapshot {
  id: number; status: Status; current_version: number | null; updated_at: string
  has_unpublished_changes: boolean; allowed: Record<string, boolean>
}
export interface VersionRow { number: number; created_at: string; restored_from: number | null; created_by_name: string }
export interface VersionDiff {
  base: number; target: number; content_changed: boolean
  changes: { field: string; before: unknown; after: unknown }[]
}
export interface QueryLog {
  id: number; user_id: number; username: string; dataset_name: string; metric: string; dimension: string
  scope: Scope; status: string; row_count: number; elapsed_ms: number; created_at: string
}
export const statusText: Record<Status, string> = { draft: '草稿', published: '已发布', archived: '已归档' }
export const scopeText: Record<Scope, string> = { own: '本人', department: '部门', all: '全部' }
export const dateText = (value: string) => new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value))
