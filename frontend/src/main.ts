import { createApp } from 'vue'
import {
  ElAlert, ElButton, ElCheckbox, ElCheckboxGroup, ElCollapse, ElCollapseItem, ElConfigProvider,
  ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty, ElInput, ElInputNumber,
  ElLoading, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag,
} from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { signOut } from './auth'
import './style.css'

window.addEventListener('lensbrief:expired', () => {
  signOut()
  void router.replace({ name: 'login', query: { next: router.currentRoute.value.fullPath } })
})
const app = createApp(App).use(router).directive('loading', ElLoading.directive)
for (const [name, component] of Object.entries({
  ElAlert, ElButton, ElCheckbox, ElCheckboxGroup, ElCollapse, ElCollapseItem, ElConfigProvider,
  ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty, ElInput, ElInputNumber,
  ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElTag,
})) {
  app.component(name, component)
}
app.mount('#app')
