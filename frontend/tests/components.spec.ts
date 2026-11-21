// @vitest-environment jsdom
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { useRoute } from 'vue-router'
import { user } from '../src/auth'
import { api } from '../src/api'
import ReportActions from '../src/components/ReportActions.vue'
import ReportsView from '../src/views/ReportsView.vue'

vi.mock('../src/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../src/api')>(), api: vi.fn(),
}))
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({ name: 'reports', query: {} as Record<string, string> })
  return {
    useRoute: () => route,
    useRouter: () => ({ push: vi.fn(), replace: ({ query }: { query: Record<string, string | undefined> }) => {
      route.query = Object.fromEntries(Object.entries(query).filter(([, value]) => value !== undefined)) as Record<string, string>
    } }),
  }
})

const table = defineComponent({ props: { data: Array }, template: '<div data-test="table">{{ data }}</div>' })
const button = defineComponent({ props: { nativeType: String }, template: '<button :type="nativeType || \'button\'"><slot /></button>' })
const input = defineComponent({
  props: { modelValue: String }, emits: ['update:modelValue'],
  template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})
const select = defineComponent({
  props: { modelValue: String }, emits: ['update:modelValue'],
  template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
})
const option = defineComponent({ props: { value: String, label: String }, template: '<option :value="value">{{ label }}</option>' })
const pagination = defineComponent({
  emits: ['update:currentPage', 'current-change'],
  template: '<button data-test="next" @click="$emit(\'update:currentPage\', 2); $emit(\'current-change\', 2)">下一页</button>',
})
const global = {
  directives: { loading: () => {} },
  stubs: { RouterLink: RouterLinkStub, ElButton: button, ElInput: input, ElSelect: select, ElOption: option,
    ElPagination: pagination, ElTable: table, ElTableColumn: true, ElAlert: true },
}

beforeEach(() => {
  vi.mocked(api).mockReset().mockResolvedValue({ items: [], total: 12, limit: 10, offset: 0 })
  useRoute().query = {}
  user.value = { id: 1, username: 'analyst', name: '运营', department_id: 1, roles: [], grants: { 'report.read': 'own' } }
})

describe('报告列表筛选', () => {
  it('首屏分别请求一次列表和状态汇总', async () => {
    vi.mocked(api).mockImplementation(async (path) => path === '/reports/summary'
      ? { total: 8, draft: 3, published: 4, archived: 1 }
      : { items: [], total: 8, limit: 10, offset: 0 })
    const wrapper = mount(ReportsView, { global })
    await flushPromises()
    expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual(['/reports?limit=10&offset=0', '/reports/summary'])
    expect(wrapper.findAll('.stat strong').map(stat => stat.text())).toEqual(['8', '3', '4', '1'])
    wrapper.unmount()
  })
  it('使用关键字和状态查询，并在筛选时重置分页', async () => {
    const wrapper = mount(ReportsView, { global })
    await flushPromises()
    await wrapper.get('[data-test="next"]').trigger('click')
    expect(vi.mocked(api).mock.lastCall?.[0]).toContain('offset=10')
    await wrapper.get('input[aria-label="搜索报告"]').setValue('  渠道  ')
    await wrapper.get('select').setValue('published')
    await wrapper.get('form').trigger('submit')
    const request = new URL(vi.mocked(api).mock.lastCall![0], 'http://test')
    expect(Object.fromEntries(request.searchParams)).toEqual({ q: '渠道', status: 'published', limit: '10', offset: '0' })
    expect(useRoute().query).toEqual({ q: '渠道', status: 'published' })
    wrapper.unmount()
  })
  it('重置按钮清空关键词与状态', async () => {
    const wrapper = mount(ReportsView, { global })
    await flushPromises()
    await wrapper.get('input[aria-label="搜索报告"]').setValue('海外')
    await wrapper.get('select').setValue('draft')
    await wrapper.findAll('button').find(item => item.text() === '重置')!.trigger('click')
    const request = new URL(vi.mocked(api).mock.lastCall![0], 'http://test')
    expect(Object.fromEntries(request.searchParams)).toEqual({ limit: '10', offset: '0' })
    wrapper.unmount()
  })
  it('从分享链接恢复搜索、状态和分页', async () => {
    useRoute().query = { q: '渠道', status: 'published', page: '2', size: '5' }
    const wrapper = mount(ReportsView, { global })
    await flushPromises()
    const request = new URL(vi.mocked(api).mock.calls[0][0], 'http://test')
    expect(Object.fromEntries(request.searchParams)).toEqual({ q: '渠道', status: 'published', limit: '5', offset: '5' })
    wrapper.unmount()
  })
})

describe('权限隐藏', () => {
  it('无创建授权时隐藏新建入口，授权后出现', async () => {
    const wrapper = mount(ReportsView, { global })
    await flushPromises()
    expect(wrapper.text()).not.toContain('新建报告')
    user.value = { ...user.value!, grants: { ...user.value!.grants, 'report.create': 'own' } }
    await flushPromises()
    expect(wrapper.text()).toContain('新建报告')
    wrapper.unmount()
  })
  it('只显示获准且当前状态允许的动作', async () => {
    const wrapper = mount(ReportActions, { global, props: { status: 'draft',
      allowed: { delete: false, publish: true, edit: false, archive: true } } })
    expect(wrapper.findAll('button').map(item => item.text())).toEqual(['发布报告'])
    await wrapper.setProps({ status: 'archived' })
    expect(wrapper.findAll('button')).toHaveLength(0)
    wrapper.unmount()
  })
})
