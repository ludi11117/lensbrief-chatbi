import type { QueryResult } from './types'

export function comparisonRows(result: QueryResult) {
  const prior = new Map(result.comparison?.rows.map(row => [row.label, row.value]))
  const rows = result.rows.map(row => {
    const current = { label: row.label, current: row.value, previous: prior.get(row.label) ?? null }
    prior.delete(row.label)
    return current
  })
  for (const [label, value] of prior) rows.push({ label, current: null, previous: value })
  return rows
}
