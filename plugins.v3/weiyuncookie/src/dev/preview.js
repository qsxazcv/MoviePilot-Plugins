/**
 * 本地开发预览入口。
 *
 * 只有在 `npm run dev` 独立预览时使用；作为 MoviePilot 联邦组件被宿主加载时，
 * 走的是 remoteEntry.js 暴露的 Page / Config，不经过这个文件。
 */
import { createApp, h } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { VApp } from 'vuetify/components'
import 'vuetify/styles'
import Config from '../components/Config.vue'

const vuetify = createVuetify({ components, directives })

const demoConfig = {
  enabled: true,
  login_type: 'wechat',
  browser_mode: 'cloakbrowser',
  check_cron: '0 */6 * * *',
  last_cookie_count: 11,
  last_status: 'Cookie 提取成功，共 11 项',
  openlist_enabled: true,
}

createApp({
  render: () =>
    h(
      VApp,
      null,
      { default: () => h(Config, { initialConfig: demoConfig }) },
    ),
})
  .use(vuetify)
  .mount('#app')
