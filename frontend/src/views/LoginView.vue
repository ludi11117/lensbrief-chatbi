<script setup lang="ts">
import BrandMark from '../components/BrandMark.vue'
import { ref, onMounted, onUnmounted } from 'vue'
import { gsap } from 'gsap'
import { useRoute, useRouter } from 'vue-router'
import { signIn } from '../auth'
import { errorText } from '../api'
import ReportCover from '../components/ReportCover.vue'

const entrance = ref<HTMLElement>()
let media: ReturnType<typeof gsap.matchMedia>
onMounted(() => {
  media = gsap.matchMedia()
  media.add('(prefers-reduced-motion: no-preference)', () => {
    gsap.timeline({ defaults: { ease: 'power3.out' } })
      .from('.headline-line > span', { yPercent: 110, duration: 0.95, stagger: 0.12 })
      .from('.login-wordmark', { xPercent: -8, autoAlpha: 0, duration: 1 }, 0.1)
      .from('.report-cover-sheet', { y: 45, autoAlpha: 0, duration: 1 }, 0.35)
      .from('.login-form', { y: 18, autoAlpha: 0, duration: 0.6, clearProps: 'transform,opacity,visibility' }, 0.3)
  }, entrance.value)
})
onUnmounted(() => media?.revert())

const route = useRoute()
const router = useRouter()
const handle = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
async function submit() {
  if (!handle.value.trim() || !password.value) { error.value = '请输入用户名和密码。'; return }
  busy.value = true
  error.value = ''
  try {
    await signIn(handle.value, password.value)
    const next = route.query.next
    await router.replace(typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/reports')
  } catch (err) { error.value = errorText(err) } finally { busy.value = false }
}
function fill(username: string) {
  handle.value = username
  password.value = 'LensBrief2026!'
  error.value = ''
}
</script>
<template>
  <main ref="entrance" class="login-layout">
    <section class="login-splash">
      <div class="brand"><BrandMark /><strong>LensBrief</strong></div>
      <a class="login-entry-link" href="#sign-in">登录工作台 ↗</a>
      <div class="login-heading" data-enter>
        <span>销售分析 · 报告协作</span><h1><span class="headline-line"><span>看清销售。</span></span><span class="headline-line"><span>写出结论。</span></span></h1>
        <p>用自然语言查询运动相机销售数据，
把业务发现写成报告，把每次发布留成版本。</p>
      </div>
      <ReportCover />
      <div class="login-wordmark" aria-hidden="true">LensBrief<span>↗</span></div>
      <p class="login-data-note">演示环境 · 销售数据、产品和账号均为虚构</p>
    </section>
    <section id="sign-in" class="login-panel">
      <form class="login-form" data-enter @submit.prevent="submit">
        <span class="login-eyebrow">YOUR NEXT REPORT STARTS HERE</span><h2>登录 LensBrief</h2>
        <p>选择演示身份，开始一份销售分析。</p>
        <el-alert v-if="error" :title="error" role="alert" type="error" :closable="false" show-icon />
        <label for="username">用户名</label><el-input id="username" v-model="handle" autocomplete="username" placeholder="输入用户名" />
        <label for="password">密码</label><el-input id="password" v-model="password" type="password" autocomplete="current-password" show-password placeholder="输入密码" />
        <el-button type="primary" native-type="submit" :loading="busy">登录</el-button>
        <div class="demo-accounts">
          <span>首次体验？选择一个演示身份</span>
          <div><el-button size="small" @click="fill('analyst')">华东分析师</el-button><el-button size="small" @click="fill('overseas')">海外分析师</el-button>
            <el-button size="small" @click="fill('manager')">部门主管</el-button><el-button size="small" @click="fill('admin')">管理员</el-button></div>
        </div>
        <p class="login-permission-note">不同身份具有不同的数据范围与操作权限。</p>
      </form>
    </section>
  </main>
</template>
