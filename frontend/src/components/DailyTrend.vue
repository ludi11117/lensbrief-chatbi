<script setup lang="ts">
import { CategoryScale, Chart, LinearScale, LineController, LineElement, PointElement, Tooltip } from 'chart.js'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { QueryResult } from '../types'

Chart.register(CategoryScale, LinearScale, LineController, LineElement, PointElement, Tooltip)

const props = defineProps<{ result: QueryResult }>()
const canvas = ref<HTMLCanvasElement>()
const formatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })
let chart: Chart<'line', (number | null)[], string> | undefined

function chartData() {
  const rows = props.result.rows
  const values = new Map(rows.map(row => [row.label, row.value]))
  const labels: string[] = []
  const step = 86_400_000
  for (let day = Date.parse(rows[0].label); day <= Date.parse(rows[rows.length - 1].label); day += step) {
    labels.push(new Date(day).toISOString().slice(0, 10))
  }
  return {
    labels,
    datasets: [{
      label: props.result.metric_name, data: labels.map(label => values.get(label) ?? null),
      borderColor: '#3459df', backgroundColor: '#3459df', borderWidth: 2,
      pointRadius: 2, pointHoverRadius: 5, spanGaps: false,
    }],
  }
}
onMounted(() => {
  if (!canvas.value) return
  chart = new Chart(canvas.value, {
    type: 'line',
    data: chartData(),
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'nearest', axis: 'x' },
      scales: {
        x: { ticks: { maxTicksLimit: 7, callback(value) { return this.getLabelForValue(Number(value)).slice(5) } },
             grid: { display: false } },
        y: { beginAtZero: true, ticks: { maxTicksLimit: 5 } },
      },
      plugins: { tooltip: { callbacks: {
        label(point) { return formatter.format(point.parsed.y ?? 0) + ' ' + props.result.unit },
      } } },
    },
  })
})
watch(() => props.result, () => {
  if (chart) {
    chart.data = chartData()
    chart.update()
  }
})
onUnmounted(() => chart?.destroy())
</script>

<template>
  <div class="daily-trend">
    <canvas ref="canvas" role="img" :aria-label="result.metric_name + '按日期趋势'"></canvas>
  </div>
</template>
