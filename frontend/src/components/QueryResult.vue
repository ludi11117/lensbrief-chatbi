<script setup lang="ts">
import { Download } from 'lucide-vue-next'
import { computed } from 'vue'
import { downloadBlob, resultCsv } from '../download'
import { scopeText, type QueryResult } from '../types'
const props = defineProps<{ result: QueryResult; exportName?: string }>()
const highest = computed(() => Math.max(1, ...props.result.rows.map(row => row.value ?? 0)))
const formatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
function exportRows() {
  const filename = (props.exportName ?? 'query-' + props.result.start + '-to-' + props.result.end) + '.csv'
  downloadBlob(new Blob([resultCsv(props.result)], { type: 'text/csv;charset=utf-8' }), filename)
}
</script>
<template>
  <section class="chart-panel">
    <div class="section-head">
      <div><h3>{{ result.metric_name }} · 按{{ result.dimension_name }}</h3><p>{{ result.start }} 至 {{ result.end }} · {{ scopeText[result.scope] }}范围</p></div>
      <el-button v-if="result.rows.length" size="small" @click="exportRows"><Download :size="15" /> 导出 CSV</el-button>
    </div>
    <el-empty v-if="!result.rows.length" description="该范围暂无结果" :image-size="65" />
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
