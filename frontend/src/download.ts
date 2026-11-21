import type { QueryResult } from './types'

function csvCell(value: string | number | null) {
  if (typeof value !== 'string') return value ?? ''
  const text = /^[\s\uFEFF]*[=+@-]/.test(value) ? "'" + value : value
  return '"' + text.replaceAll('"', '""') + '"'
}

export function resultCsv(result: QueryResult) {
  const header = [result.dimension_name, result.metric_name + ' (' + result.unit + ')']
  const rows = result.rows.map(row => [row.label, row.value])
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
