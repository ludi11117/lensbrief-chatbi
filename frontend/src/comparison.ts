import type { QueryResult } from './types'

export const changeUnit = (unit: string) => unit === '%' ? '百分点' : unit

export function comparisonRows(result: QueryResult) {
  const prior = new Map(result.comparison?.rows.map(row => [row.label, row.value]))
  const rows = result.rows.map(row => {
    const current = row.value
    const previous = prior.get(row.label) ?? null
    const change = current === null || previous === null ? null : Number((current - previous).toFixed(2))
    prior.delete(row.label)
    return { label: row.label, current, previous, change }
  })
  for (const [label, value] of prior) rows.push({ label, current: null, previous: value, change: null })
  return rows
}
