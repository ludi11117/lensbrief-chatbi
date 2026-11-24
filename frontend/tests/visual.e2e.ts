import { expect, test } from '@playwright/test'

test('手机报告卡片筛选、空状态与详情入口', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.getByRole('link', { name: '登录工作台 ↗' }).click()
  await page.getByRole('button', { name: '华东分析师' }).click()
  await page.getByRole('button', { name: '登录', exact: true }).click()
  const card = page.locator('.mobile-report-card').first()
  await expect(card).toBeVisible()
  await expect(page.locator('.desktop-report-table')).toBeHidden()
  const title = await card.locator('h3').innerText()
  await page.getByRole('textbox', { name: '搜索报告' }).fill('不存在的报告-visual-test')
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  await expect(page.locator('.report-empty')).toBeVisible()
  await page.getByRole('button', { name: '重置筛选', exact: true }).click()
  await expect(card).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await card.click()
  await expect(page.getByRole('heading', { name: title, exact: true }).first()).toBeVisible()
})

test('图表动画可暂停，并响应减少动态效果偏好', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: '暂停图表动画' }).click()
  const trace = page.locator('.cover-bar').first()
  const offset = await trace.evaluate(el => getComputedStyle(el).transform)
  await expect(page.getByRole('button', { name: '播放图表动画' })).toHaveAttribute('aria-pressed', 'true')
  // 通过浏览器帧比较暂停前后的图表，而不是匹配实现中的时间轴配置。
  const afterFrames = await trace.evaluate(el => new Promise<string>(resolve => {
    let frames = 0
    function frame() { if (++frames === 12) resolve(getComputedStyle(el).transform); else requestAnimationFrame(frame) }
    requestAnimationFrame(frame)
  }))
  expect(afterFrames).toBe(offset)
  await page.getByRole('button', { name: '播放图表动画' }).click()
  await expect.poll(() => trace.evaluate(el => getComputedStyle(el).transform), { timeout: 12_000, intervals: [100] }).not.toBe(offset)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(page.locator('.flow-control')).toBeHidden()
  await expect(page.getByRole('article', { name: '十月渠道销售额演示报告' })).toBeVisible()
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  await expect.poll(() => trace.evaluate(el => getComputedStyle(el).transform)).toBe('none')
})
