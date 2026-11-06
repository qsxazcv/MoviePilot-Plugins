import { createApp, h } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import Config from '../components/Config.vue'
import Page from '../components/Page.vue'

const q = new URLSearchParams(location.search)
const which = q.get('view') || 'config'
const withCookie = q.get('cookie') !== '0'

const configDemo = {
  enabled: true, login_type: 'wechat', check_cron: '0 */6 * * *',
  last_cookie_count: 10, last_status: 'Cookie 提取成功，共 10 项', openlist_enabled: true,
}

const statusDemo = {
  enabled: true, running: false,
  login_type_title: '微信扫码登录', browser_mode_title: 'CloakBrowser',
  check_cron: '0 */6 * * *', cookie_count: withCookie ? 10 : 0,
  has_cookie: withCookie, has_qrcode: false, qrcode: '',
  last_status: withCookie ? 'Cookie 提取成功，共 10 项' : '尚未运行',
  last_run: withCookie ? '2026-11-06 12:45:52' : '',
  last_check: withCookie ? '2026-11-06 12:46:05' : '',
  last_check_status: withCookie ? '扫码后 Cookie 已刷新' : '未检测',
  last_openlist_sync: withCookie ? '2026-11-06 12:46:05' : '',
  last_openlist_sync_status: withCookie ? '同步成功：已更新 OpenList 存储 2 的 Cookie' : '未同步',
}

const fakeApi = {
  get: async (path) => (path.endsWith('status') ? { data: statusDemo } : { data: {} }),
  post: async () => ({ data: { success: true, message: 'ok' } }),
}

const vuetify = createVuetify({ components, directives })
const Target = which === 'page' ? Page : Config
const props = which === 'page' ? { api: fakeApi } : { initialConfig: configDemo }

createApp({ render: () => h(components.VApp, null, () => h(Target, props)) })
  .use(vuetify)
  .mount('#app')
