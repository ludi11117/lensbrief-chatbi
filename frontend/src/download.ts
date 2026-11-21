import type { QueryResult } from './types'
import { comparisonRows } from './comparison'

function csvCell(value: string | number | null) {
  if (typeof value !== 'string') return value ?? ''
  const text = /^[\s\uFEFF]*[=+@-]/.test(value) ? "'" + value : value
  return '"' + text.replaceAll('"', '""') + '"'
}

export function resultCsv(result: QueryResult) {
  const measure = result.metric_name + ' (' + result.unit + ')'
  const previous = result.comparison
  const header = [result.dimension_name, measure]
  if (previous) {
    header[1] = `本期 ${measure} ${result.start} 至 ${result.end}`
    header.push(`对照期 ${measure} ${previous.start} 至 ${previous.end}`)
  }
  const rows = previous
    ? comparisonRows(result).map(row => [row.label, row.current, row.previous])
    : result.rows.map(row => [row.label, row.value])
  const channel = result.channel
  if (channel) {
    header.push('渠道筛选')
    rows.forEach(row => row.push(channel))
  }
  return '\uFEFF' + [header, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function downloadBlob(file: Blob, filename: string) {
  const href = URL.createObjectURL(file)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
