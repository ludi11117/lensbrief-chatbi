import { describe, expect, it } from 'vitest'
import { resultCsv } from '../src/download'
import type { QueryResult } from '../src/types'

const result: QueryResult = {
  metric_name: '销售额', dimension_name: '渠道', metric_note: '', unit: '元',
  start: '2026-10-01', end: '2026-10-31', scope: 'own', rows: [],
}

describe('查询 CSV', () => {
  it('保留数值精度并对含逗号、引号和换行的标签正确转义', () => {
    const content = resultCsv({ ...result, rows: [{ label: '门店,"周会"\n复盘', value: 1234.56789 }] })
    expect(content).toBe('\uFEFF"渠道","销售额 (元)"\r\n"门店,""周会""\n复盘",1234.56789\r\n')
  })
  it('公式前缀按文本导出，空值保持空，负数仍为数值', () => {
    const content = resultCsv({ ...result, rows: [{ label: '=1+1', value: null }, { label: '无退款', value: -10 }] })
    expect(content).toContain('"\'=1+1",\r\n"无退款",-10\r\n')
  })
  it('对照查询导出两个区间，保留只在某一期出现的分组', () => {
    const content = resultCsv({
      ...result, rows: [{ label: '官网', value: 0 }, { label: '零售', value: 15 }],
      comparison: { start: '2026-08-31', end: '2026-09-30', rows: [{ label: '官网', value: 20 }, { label: '电商', value: 12 }] },
    })
    expect(content).toContain('"本期 销售额 (元) 2026-10-01 至 2026-10-31","对照期 销售额 (元) 2026-08-31 至 2026-09-30"')
    expect(content).toContain('"官网",0,20\r\n"零售",15,\r\n"电商",,12\r\n')
  })
})
