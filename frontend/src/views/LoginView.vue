<script setup lang="ts">
import { ScanLine } from 'lucide-vue-next'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { signIn } from '../auth'
import { errorText } from '../api'

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
  <main class="login-layout">
    <section class="login-splash">
      <div class="brand"><span class="brand-mark"><ScanLine :size="22" /></span><strong>LensBrief</strong></div>
      <div class="login-heading"><span>数据运营工作台</span><h1>从指标到报告</h1><p>汇总运动相机销售数据，整理业务发现，并通过版本记录保留每次发布的依据。</p></div>
    </section>
    <section class="login-panel">
      <form class="login-form" @submit.prevent="submit">
        <h2>登录 LensBrief</h2>
        <p>登录后查看你有权限访问的报告和查询记录。</p>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <label for="username">用户名</label><el-input id="username" v-model="handle" autocomplete="username" placeholder="输入用户名" />
        <label for="password">密码</label><el-input id="password" v-model="password" type="password" autocomplete="current-password" show-password placeholder="输入密码" />
        <el-button type="primary" native-type="submit" :loading="busy">登录</el-button>
        <div class="demo-accounts">
          <span>填入演示账号</span>
          <div><el-button size="small" @click="fill('analyst')">华东分析师</el-button><el-button size="small" @click="fill('overseas')">海外分析师</el-button>
            <el-button size="small" @click="fill('manager')">部门主管</el-button><el-button size="small" @click="fill('admin')">管理员</el-button></div>
        </div>
      </form>
    </section>
  </main>
</template>
