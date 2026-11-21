<script setup lang="ts">
import { Download } from 'lucide-vue-next'
import { computed, defineAsyncComponent } from 'vue'
import { changeUnit, comparisonRows } from '../comparison'
import { downloadBlob, resultCsv } from '../download'
import { scopeText, type QueryResult } from '../types'
const props = defineProps<{ result: QueryResult; exportName?: string }>()
const DailyTrend = defineAsyncComponent(() => import('./DailyTrend.vue'))
const isDaily = computed(() => props.result.dimension_code === 'day'
  || (!props.result.dimension_code && props.result.dimension_name === '日期'))
const comparisons = computed(() => props.result.comparison ? comparisonRows(props.result) : [])
const highest = computed(() => Math.max(1, ...props.result.rows.map(row => row.value ?? 0)))
const formatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
const changeFormatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2, signDisplay: 'exceptZero' })
function exportRows() {
  const filename = (props.exportName ?? 'query-' + props.result.start + '-to-' + props.result.end) + '.csv'
  downloadBlob(new Blob([resultCsv(props.result)], { type: 'text/csv;charset=utf-8' }), filename)
}
</script>
<template>
  <section class="chart-panel">
    <div class="section-head">
      <div><h3>{{ result.metric_name }} · 按{{ result.dimension_name }}</h3><p>{{ result.start }} 至 {{ result.end }} · {{ scopeText[result.scope] }}范围</p>
        <p v-if="result.channel">渠道筛选 · {{ result.channel }}</p></div>
      <el-button v-if="result.rows.length || comparisons.length" size="small" @click="exportRows"><Download :size="15" /> 导出 CSV</el-button>
    </div>
    <template v-if="result.comparison">
      <p class="comparison-period">对照期 {{ result.comparison.start }} 至 {{ result.comparison.end }}</p>
      <el-table v-if="comparisons.length" :data="comparisons" max-height="330">
        <el-table-column prop="label" :label="result.dimension_name" />
        <el-table-column :label="'本期 / ' + result.unit"><template #default="{ row }">{{ row.current === null ? '—' : formatter.format(row.current) }}</template></el-table-column>
        <el-table-column :label="'对照期 / ' + result.unit"><template #default="{ row }">{{ row.previous === null ? '—' : formatter.format(row.previous) }}</template></el-table-column>
        <el-table-column :label="'差值 / ' + changeUnit(result.unit)"><template #default="{ row }">{{ row.change === null ? '—' : changeFormatter.format(row.change) }}</template></el-table-column>
      </el-table>
      <el-empty v-else description="两个区间均暂无结果" :image-size="65" />
    </template>
    <el-empty v-else-if="!result.rows.length" description="该范围暂无结果" :image-size="65" />
    <template v-else-if="isDaily">
      <DailyTrend :result="result" />
      <details class="daily-values">
        <summary>查看日期明细</summary>
        <el-table :data="result.rows" max-height="330">
          <el-table-column prop="label" label="日期" />
          <el-table-column prop="value" :label="result.metric_name + ' / ' + result.unit" />
        </el-table>
      </details>
    </template>
    <div v-else-if="result.rows.length <= 8" class="chart-rows">
      <div v-for="row in result.rows" :key="row.label" class="chart-row">
        <span>{{ row.label }}</span><div class="bar-track"><div class="bar" :style="{ width: (row.value ?? 0) / highest * 100 + '%' }"></div></div>
        <strong>{{ row.value === null ? '—' : formatter.format(row.value) }} {{ result.unit }}</strong>
      </div>
    </div>
    <el-table v-else :data="result.rows" max-height="330">
      <el-table-column prop="label" :label="result.dimension_name" />
      <el-table-column prop="value" :label="result.metric_name + ' / ' + result.unit" />
    </el-table>
    <p class="chart-note">{{ result.metric_note }}</p>
    <details v-if="result.knowledge" class="knowledge-reference">
      <summary>{{ result.knowledge.title }} · 知识包 v{{ result.knowledge.revision }}</summary>
      <ul><li v-for="(item, index) in result.knowledge.items" :key="index"><strong>{{ item.title }}</strong> · {{ item.content }}</li></ul>
    </details>
  </section>
</template>
