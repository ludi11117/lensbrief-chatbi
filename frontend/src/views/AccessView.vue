<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { api, errorText, params } from '../api'
import { hasGrant, user } from '../auth'
import { dateText, scopeText, type Page, type Scope } from '../types'
type Person = { id: number; name: string; username: string; department: string; roles: string[] }
type Role = { id: number; code: string; name: string; grants: Record<string, Scope> }
type Audit = { id: number; username: string; action: string; resource: string; resource_id: number | null; created_at: string }
const people = ref<Person[]>([])
const roles = ref<Role[]>([])
const logs = ref<Audit[]>([])
const auditPage = ref(1)
const auditTotal = ref(0)
const editing = ref<Person>()
const choices = ref<string[]>([])
const dialog = ref(false)
const error = ref('')
const saving = ref(false)
async function load() {
  try {
    const access = await api<{ users: Person[]; roles: Role[] }>('/access')
    people.value = access.users; roles.value = access.roles
    if (hasGrant('audit.read')) await loadAudit()
  } catch (err) { error.value = errorText(err) }
}
async function loadAudit() {
  try {
    const result = await api<Page<Audit>>('/audit' + params({ limit: 10, offset: (auditPage.value - 1) * 10 }))
    logs.value = result.items; auditTotal.value = result.total
  } catch (err) { error.value = errorText(err) }
}
function edit(person: Person) { editing.value = person; choices.value = [...person.roles]; dialog.value = true }
async function save() {
  if (!editing.value) return
  saving.value = true
  error.value = ''
  try {
    await api('/access/users/' + editing.value.id + '/roles', { method: 'PUT', body: JSON.stringify({ roles: choices.value }) })
    dialog.value = false
    ElMessage.success('角色已更新')
    await load()
  } catch (err) { error.value = errorText(err); dialog.value = false } finally { saving.value = false }
}
const roleName = (code: string) => roles.value.find(role => role.code === code)?.name ?? code
onMounted(load)
</script>
<template>
  <div class="page-title"><h1>权限管理</h1><p>分配用户角色并查看报告操作及越权审计记录。</p></div>
  <el-alert v-if="error" class="page-alert" :title="error" type="error" :closable="false" />
  <div class="stack">
    <section class="panel">
      <div class="section-head"><h2>用户与角色</h2></div>
      <el-table :data="people">
        <el-table-column prop="id" label="用户 ID" width="90" /><el-table-column prop="name" label="姓名" min-width="105" />
        <el-table-column prop="username" label="账号" min-width="115" /><el-table-column prop="department" label="部门" min-width="115" />
        <el-table-column label="已分配角色" min-width="170"><template #default="{ row }">
          <el-tag v-for="role in row.roles" :key="role" effect="plain" class="role-tag">{{ roleName(role) }}</el-tag>
          <span v-if="!row.roles.length" class="muted">未分配</span></template></el-table-column>
        <el-table-column label="操作" min-width="110"><template #default="{ row }"><el-button v-if="row.id !== user?.id" text type="primary" @click="edit(row)">分配角色</el-button><span v-else class="muted">当前账号</span></template></el-table-column>
      </el-table>
      <el-collapse><el-collapse-item v-for="role in roles" :key="role.code" :title="role.name">
        <div class="grant-grid"><div v-for="(scope, code) in role.grants" :key="code"><code>{{ code }}</code><span>{{ scopeText[scope] }}</span></div></div>
      </el-collapse-item></el-collapse>
    </section>
    <section v-if="hasGrant('audit.read')" class="panel">
      <div class="section-head"><h2>操作审计</h2><span class="muted">{{ auditTotal }} 条记录</span></div>
      <el-table :data="logs" empty-text="暂无审计记录">
        <el-table-column prop="username" label="用户" min-width="100" /><el-table-column prop="action" label="动作" min-width="165" />
        <el-table-column label="资源" min-width="125"><template #default="{ row }">{{ row.resource }} {{ row.resource_id ? '#' + row.resource_id : '' }}</template></el-table-column>
        <el-table-column label="时间" min-width="168"><template #default="{ row }">{{ dateText(row.created_at) }}</template></el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="auditPage" :page-size="10" :total="auditTotal" background layout="prev, pager, next" @current-change="loadAudit" /></div>
    </section>
  </div>
  <el-dialog v-model="dialog" :title="'分配角色 · ' + editing?.name" width="min(500px, 94vw)">
    <el-checkbox-group v-model="choices"><el-checkbox v-for="role in roles" :key="role.code" :value="role.code">{{ role.name }}</el-checkbox></el-checkbox-group>
    <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存角色</el-button></template>
  </el-dialog>
</template>
