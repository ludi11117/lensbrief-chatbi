<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { FileText, GitCompareArrows, History, Link2, Printer } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, api, errorText, params } from '../api'
import QueryPreview from '../components/QueryResult.vue'
import ReportActions from '../components/ReportActions.vue'
import StatusPill from '../components/StatusPill.vue'
import VersionFeedback from '../components/VersionFeedback.vue'
import { dateText, scopeText, type Page, type Report, type Scope, type Snapshot, type VersionDiff, type VersionRow } from '../types'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const path = '/reports/' + id
const report = ref<Report>()
const versions = ref<VersionRow[]>([])
const versionsTotal = ref(0)
const historyPage = ref(1)
const selected = ref<Snapshot | null>(null)
const selectedNumber = ref<number | null>(null)
const compareOpen = ref(false)
const base = ref<number>()
const target = ref<number>()
const comparison = ref<VersionDiff>()
const compareError = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const errorCode = ref<number>()
const showing = computed(() => selected.value ?? report.value)
const discussionVersion = computed(() => selectedNumber.value ??
  (report.value?.has_unpublished_changes ? null : report.value?.current_version))
const previewLabel = computed(() => {
  if (selectedNumber.value) return '历史版本 v' + selectedNumber.value
  if (report.value?.status === 'archived') return '归档版本 v' + report.value.current_version
  if (report.value?.current_version && !report.value.allowed.edit) return '发布版 v' + report.value.current_version
  return '当前工作稿'
})
const printable = ref<HTMLElement>()
const expandedForPrint: HTMLDetailsElement[] = []
const labels: Record<string, string> = {
  title: '标题', description: '摘要', dataset_id: '数据集', query_id: '查询记录', asset_ids: '附件 ID',
  metric_name: '指标', dimension_name: '分组维度', scope: '数据范围', start: '开始日期', end: '结束日期',
  channel: '渠道', comparison_window: '对照期', knowledge_pack: '知识包',
}
const format = (field: string, value: unknown) => {
  if (field === 'scope' && value) return scopeText[value as Scope]
  return Array.isArray(value) ? value.join('、') || '—' : String(value ?? '—')
}
function diffStyle(line: string, index: number) {
  if (index < 2 || line.startsWith('@@')) return 'diff-meta'
  if (line.startsWith('+')) return 'diff-added'
  if (line.startsWith('-')) return 'diff-removed'
  return ''
}
let previewRequest = 0

async function loadVersions() {
  const history = await api<Page<VersionRow>>(path + '/versions' + params({ limit: 10, offset: (historyPage.value - 1) * 10 }))
  versions.value = history.items
  versionsTotal.value = history.total
}
async function changeHistory() {
  try { await loadVersions() } catch (err) { error.value = errorText(err) }
}
async function load() {
  loading.value = true
  error.value = ''
  try { report.value = await api<Report>(path); await loadVersions() }
  catch (err) { error.value = errorText(err); errorCode.value = err instanceof ApiError ? err.status : undefined }
  finally { loading.value = false }
}
function beforePrint() {
  for (const details of printable.value?.querySelectorAll<HTMLDetailsElement>('details:not([open])') ?? []) {
    expandedForPrint.push(details)
    details.open = true
  }
}
function afterPrint() {
  for (const details of expandedForPrint.splice(0)) details.open = false
}
function printReport() { window.print() }

onMounted(async () => {
  window.addEventListener('beforeprint', beforePrint)
  window.addEventListener('afterprint', afterPrint)
  await load()
  if (report.value) await previewRouteVersion()
})
onUnmounted(() => {
  window.removeEventListener('beforeprint', beforePrint)
  window.removeEventListener('afterprint', afterPrint)
})
watch(() => route.query.version, () => { if (report.value) void previewRouteVersion() })

function previewRouteVersion() {
  const version = Number(route.query.version)
  if (typeof route.query.version === 'string' && Number.isSafeInteger(version) && version > 0) return preview(version)
  return preview(null)
}
function selectVersion(number: number | null) {
  return router.replace({ query: { ...route.query, version: number?.toString() } })
}

async function copyVersionLink(number: number) {
  const { href } = router.resolve({ name: 'report', params: { id }, query: { version: number } })
  try {
    await navigator.clipboard.writeText(new URL(href, window.location.origin).href)
    ElMessage.success('已复制 v' + number + ' 的链接')
  } catch {
    await selectVersion(number)
    ElMessage.info('可从地址栏复制此版本链接。')
  }
}

async function preview(number: number | null) {
  const request = ++previewRequest
  if (number === null) { selected.value = null; selectedNumber.value = null; return }
  error.value = ''
  try {
    const snapshot = await api<Snapshot>(path + '/versions/' + number)
    if (request === previewRequest) { selected.value = snapshot; selectedNumber.value = number }
  } catch (err) { if (request === previewRequest) error.value = errorText(err) }
}
function openCompare() {
  target.value = report.value?.current_version ?? undefined
  base.value = target.value ? target.value - 1 : undefined
  compareOpen.value = true
  comparison.value = undefined
  compareError.value = ''
}
async function compare() {
  compareError.value = ''
  comparison.value = undefined
  if (!base.value || !target.value || base.value === target.value) { compareError.value = '请输入两个不同的版本号。'; return }
  try { comparison.value = await api<VersionDiff>(path + '/versions/diff' + params({ base: base.value, target: target.value })) }
  catch (err) { compareError.value = errorText(err) }
}
async function perform(action: 'publish' | 'archive' | 'remove' | 'rollback', number?: number) {
  const headers = report.value ? { 'If-Match': report.value.etag } : undefined
  const prompts = {
    publish: '发布会将当前工作稿保存为一个新版本。',
    archive: '归档后显示最后发布的版本，仍可查看历史版本。归档后会关闭编辑和发布。',
    remove: '删除后此报告将从报告中心移除。',
    rollback: '将 v' + number + ' 的内容恢复为一个新的发布版本，保留现有版本。',
  }
  try { await ElMessageBox.confirm(prompts[action], '确认操作', { confirmButtonText: '确认', cancelButtonText: '取消' }) }
  catch { return }
  busy.value = true
  error.value = ''
  try {
    if (action === 'remove') {
      await api(path, { method: 'DELETE', headers })
      ElMessage.success('报告已删除')
      await router.push('/reports')
      return
    }
    const suffix = action === 'rollback' ? 'rollback/' + number : action
    await api(path + '/' + suffix, { method: 'POST', headers })
    ElMessage.success({ publish: '已发布新版本', archive: '报告已归档', rollback: '已回滚并发布新版本' }[action])
    historyPage.value = 1
    await selectVersion(null)
    await load()
  } catch (err) {
    if (err instanceof ApiError && err.status === 412) {
      await load()
      if (!error.value) error.value = '报告已被更新。页面已加载最新工作稿，请核对后再操作。'
    } else error.value = errorText(err)
  } finally { busy.value = false }
}
</script>
<template>
  <RouterLink class="text-link print-hide" to="/reports">返回报告中心</RouterLink>
  <el-alert v-if="error" class="page-alert print-hide" :title="errorCode ? errorCode + ' · ' + error : error" type="error" show-icon :closable="false" />
  <div v-loading="loading" class="detail-page">
    <template v-if="report && showing">
      <div class="page-title split print-hide">
        <div><div class="inline"><StatusPill :status="report.status" /><span v-if="report.current_version" class="muted">当前发布 v{{ report.current_version }}</span></div>
          <h1>{{ report.title }}</h1><p>更新于 {{ dateText(report.updated_at) }}<span v-if="report.has_unpublished_changes"> · 工作稿有未发布更改</span></p></div>
        <ReportActions :status="report.status" :allowed="report.allowed" :loading="busy" @edit="router.push(path + '/edit')" @publish="perform('publish')" @archive="perform('archive')" @remove="perform('remove')" />
      </div>
      <div class="detail-grid">
        <article ref="printable" class="panel printable-report">
          <div class="section-head print-hide"><h2>报告预览</h2>
            <div class="inline"><span class="version-label">{{ previewLabel }}</span>
              <el-button v-if="discussionVersion" size="small" @click="copyVersionLink(discussionVersion)"><Link2 :size="15" /> 复制版本链接</el-button>
              <el-button size="small" @click="printReport"><Printer :size="15" /> 打印报告</el-button></div>
          </div>
          <div class="print-heading"><span>LensBrief · {{ discussionVersion ? 'v' + discussionVersion : '工作稿' }}</span><h1>{{ showing.title }}</h1></div>
          <h3 class="preview-title print-hide">{{ showing.title }}</h3>
          <p v-if="showing.description" class="preview-description">{{ showing.description }}</p>
          <QueryPreview v-if="showing.query" :result="showing.query"
                        :export-name="'report-' + id + (discussionVersion ? '-v' + discussionVersion : '-draft')" />
          <div class="report-body">{{ showing.content || '暂无正文。' }}</div>
          <div v-if="showing.assets.length" class="attachment-list">
            <h3>附件</h3>
            <RouterLink v-for="file in showing.assets" :key="file.id" class="attachment"
                        :to="{ name: 'asset', params: { asset: file.id }, query: {
                          report: id, version: discussionVersion ?? undefined,
                        } }">
              <FileText :size="17" /><span>{{ file.filename }}</span><strong>预览</strong>
            </RouterLink>
          </div>
          <VersionFeedback v-if="discussionVersion" :key="discussionVersion" :report-path="path"
                           :version="discussionVersion" :archived="report.status === 'archived'" />
          <p v-else-if="report.current_version" class="muted version-feedback">选择一个已发布版本查看反馈。</p>
        </article>
        <section class="panel version-panel">
          <div class="section-head"><h2><History :size="19" /> 版本记录</h2><el-button v-if="versionsTotal >= 2" size="small" @click="openCompare"><GitCompareArrows :size="15" /> 对比版本</el-button></div>
          <el-empty v-if="!versions.length" description="发布报告后将生成版本" :image-size="60" />
          <template v-else>
            <el-button v-if="selectedNumber" text type="primary" @click="selectVersion(null)">返回当前内容</el-button>
            <div v-for="version in versions" :key="version.number" class="version-item" :class="{ selected: selectedNumber === version.number }">
              <button class="version-button" type="button" @click="selectVersion(version.number)">
                <strong>v{{ version.number }} <span v-if="version.number === report.current_version" class="status-pill published">当前</span></strong>
                <small>{{ dateText(version.created_at) }} · {{ version.created_by_name }}</small>
                <small v-if="version.restored_from">恢复自 v{{ version.restored_from }}</small>
              </button>
              <el-button v-if="report.allowed.rollback && report.status === 'published' && version.number !== report.current_version" text type="primary" :disabled="busy" @click="perform('rollback', version.number)">回滚</el-button>
            </div>
            <el-pagination v-if="versionsTotal > 10" v-model:current-page="historyPage" :total="versionsTotal" :page-size="10" layout="prev, pager, next" @current-change="changeHistory" />
          </template>
        </section>
      </div>
    </template>
  </div>
  <el-dialog v-model="compareOpen" title="版本对比" width="min(760px, 94vw)">
    <div class="compare-controls"><label>基准版本 <el-input-number v-model="base" :min="1" :max="report?.current_version ?? 1" /></label>
      <label>目标版本 <el-input-number v-model="target" :min="1" :max="report?.current_version ?? 1" /></label>
      <el-button type="primary" @click="compare">开始对比</el-button></div>
    <el-alert v-if="compareError" :title="compareError" type="error" :closable="false" />
    <template v-if="comparison">
      <template v-for="group in [{ title: '报告字段', rows: comparison.changes }, { title: '查询条件', rows: comparison.query_changes }]" :key="group.title">
        <template v-if="group.rows.length">
          <h3 class="content-diff-heading">{{ group.title }}</h3>
          <el-table :data="group.rows">
            <el-table-column label="字段"><template #default="{ row }">{{ labels[row.field] || row.field }}</template></el-table-column>
            <el-table-column label="原值"><template #default="{ row }">{{ format(row.field, row.before) }}</template></el-table-column>
            <el-table-column label="新值"><template #default="{ row }">{{ format(row.field, row.after) }}</template></el-table-column>
          </el-table>
        </template>
      </template>
      <p v-if="!comparison.changes.length && !comparison.query_changes.length">元数据相同。</p>
      <h3 class="content-diff-heading">正文变更</h3>
      <pre v-if="comparison.content_changed" class="content-diff" tabindex="0" aria-label="正文逐行对比"><span
        v-for="(line, index) in comparison.content_diff" :key="index" :class="diffStyle(line, index)">{{ line }}</span></pre>
      <p v-else>正文相同。</p>
    </template>
  </el-dialog>
</template>
