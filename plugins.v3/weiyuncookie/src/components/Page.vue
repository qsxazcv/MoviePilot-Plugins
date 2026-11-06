<template>
  <div class="wy-page">
    <VToolbar class="wy-toolbar" density="comfortable">
      <VToolbarTitle>微云 Cookie 助手</VToolbarTitle>
      <VBtn icon="mdi-play-circle-outline" variant="text" title="启动扫码登录" :loading="busy" @click="action('start_login', '已启动微云扫码登录')" />
      <VBtn icon="mdi-shield-check-outline" variant="text" title="立即检测" :loading="busy" @click="action('check_cookie', '检测完成')" />
      <VBtn icon="mdi-cloud-sync-outline" variant="text" title="同步 OpenList" :loading="busy" @click="action('sync_openlist', '同步完成')" />
      <VBtn icon="mdi-refresh" variant="text" title="刷新" :loading="loading" @click="load()" />
      <VBtn icon="mdi-cog-outline" variant="text" title="设置" @click="$emit('switch')" />
      <VBtn icon="mdi-close" variant="text" title="关闭" @click="$emit('close')" />
    </VToolbar>

    <div class="wy-page-wrap">
      <VAlert v-if="error" type="error" variant="tonal" class="mb-3">{{ error }}</VAlert>
      <VAlert v-if="message" type="success" variant="tonal" class="mb-3" closable @click:close="clearMessage">
        {{ message }}
      </VAlert>

      <div v-if="loading" class="wy-loading">
        <VProgressCircular indeterminate color="primary" />
        <span>正在读取微云状态...</span>
      </div>

      <!-- 状态总览：状态与两个关键动作放一起，避免到处找按钮 -->
      <div class="wy-summary">
        <div class="wy-summary-main">
          <div class="wy-summary-title">扫码登录与 Cookie 状态</div>
          <div class="wy-summary-sub">{{ status.last_status || '尚未运行' }}</div>
        </div>
        <div class="wy-summary-actions">
          <VChip :color="stateColor" variant="tonal" size="small">{{ stateText }}</VChip>
          <VChip :color="status.enabled ? 'success' : 'default'" variant="tonal" size="small">
            {{ status.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VBtn size="small" color="primary" prepend-icon="mdi-play-circle-outline" :loading="busy" @click="action('start_login', '已启动微云扫码登录')">
            启动扫码
          </VBtn>
          <VBtn size="small" variant="tonal" prepend-icon="mdi-content-copy" :disabled="!status.has_cookie" @click="copyCookie">
            复制 Cookie
          </VBtn>
        </div>
      </div>

      <div class="wy-status-strip">
        <div v-for="item in statusStats" :key="item.label" class="wy-status-item">
          <div class="wy-status-label">
            <VIcon :icon="item.icon" size="15" :color="item.color" class="mr-1" />{{ item.label }}
          </div>
          <div class="wy-status-value" :title="item.value">{{ item.value || '—' }}</div>
        </div>
      </div>

      <!-- 主区：二维码与运行记录合并，左右等高 -->
      <VRow dense class="wy-main-grid mt-2">
        <VCol cols="12" md="5" class="wy-col-flex">
          <VCard variant="outlined" class="wy-card-panel wy-card-fill">
            <VCardText class="wy-card-body">
              <div class="wy-section-line">
                <span>二维码</span>
                <VBtn size="small" variant="text" prepend-icon="mdi-delete-outline" color="error" :loading="busy" @click="action('clear_cookie', '已清除 Cookie')">
                  清除
                </VBtn>
              </div>

              <!-- 有码时展开大图；没码时只占一行提示，不浪费版面 -->
              <div v-if="qrcodeSrc" class="wy-qr-panel">
                <img :src="qrcodeSrc" class="wy-qr-img" alt="微云登录二维码" />
              </div>
              <button v-else type="button" class="wy-qr-idle" :disabled="busy" @click="action('start_login', '已启动微云扫码登录')">
                <VIcon icon="mdi-qrcode-scan" size="26" />
                <span>点击生成登录二维码</span>
              </button>

              <!-- 没有二维码时用三步引导填住空白，而不是留一大片空 -->
              <ol v-if="!qrcodeSrc" class="wy-steps">
                <li v-for="step in steps" :key="step.title">
                  <VIcon :icon="step.icon" size="16" />
                  <div>
                    <div class="wy-step-title">{{ step.title }}</div>
                    <div class="wy-step-desc">{{ step.desc }}</div>
                  </div>
                </li>
              </ol>

              <div class="wy-action-row wy-action-row--stack">
                <VBtn color="primary" prepend-icon="mdi-play-circle-outline" :loading="busy" block @click="action('start_login', '已启动微云扫码登录')">
                  {{ qrcodeSrc ? '重新生成二维码' : '启动扫码' }}
                </VBtn>
                <div class="wy-action-pair">
                  <VBtn variant="text" size="small" prepend-icon="mdi-shield-check-outline" :loading="busy" @click="action('check_cookie', '检测完成')">
                    检测 Cookie
                  </VBtn>
                  <VBtn variant="text" size="small" prepend-icon="mdi-cloud-sync-outline" :loading="busy" @click="action('sync_openlist', '同步完成')">
                    同步 OpenList
                  </VBtn>
                </div>
              </div>
            </VCardText>
          </VCard>
        </VCol>

        <VCol cols="12" md="7" class="wy-col-flex">
          <VCard variant="outlined" class="wy-card-panel wy-card-fill">
            <VCardText class="wy-card-body">
              <div class="wy-section-line"><span>运行记录</span></div>

              <div class="wy-cookie-state" :class="{ 'is-empty': !status.has_cookie }">
                <VIcon :icon="status.has_cookie ? 'mdi-shield-lock-outline' : 'mdi-cookie-alert-outline'" size="24" :color="status.has_cookie ? 'success' : 'grey'" />
                <div class="wy-cookie-state-body">
                  <div class="wy-cookie-state-title">{{ status.has_cookie ? 'Cookie 已安全保存' : '暂无 Cookie' }}</div>
                  <div class="wy-cookie-state-desc">
                    {{ status.has_cookie
                      ? `已保存 ${status.cookie_count ?? 0} 个 Cookie，明文默认隐藏。`
                      : '启动扫码登录后会自动保存 Cookie。' }}
                  </div>
                </div>
              </div>

              <div class="wy-timeline-grid">
                <div v-for="item in timeline" :key="item.label" class="wy-timeline-row">
                  <VIcon :icon="item.icon" :color="item.color" size="16" />
                  <div class="wy-timeline-body">
                    <div class="wy-timeline-label">{{ item.label }}</div>
                    <div class="wy-timeline-value" :title="item.value">{{ item.value || '—' }}</div>
                  </div>
                </div>
              </div>

              <div class="wy-tip">
                <VIcon icon="mdi-lightbulb-on-outline" size="15" />
                <span>{{ tipText }}</span>
              </div>
            </VCardText>
          </VCard>
        </VCol>
      </VRow>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getPluginApi, postPluginApi } from '../api.js'
import { humanizeCron } from './Config.vue'
import '../styles/page.css'

export default {
  name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(props) {
    const loading = ref(false)
    const busy = ref(false)
    const error = ref('')
    const message = ref('')
    const status = ref({})
    let timer = null
    let messageTimer = null

    const qrcodeSrc = computed(() => (status.value?.has_qrcode && status.value?.qrcode ? status.value.qrcode : ''))
    const stateColor = computed(() => (status.value.running ? 'warning' : status.value.has_cookie ? 'success' : 'default'))
    const stateText = computed(() => (status.value.running ? '扫码进行中' : status.value.has_cookie ? 'Cookie 已保存' : '等待登录'))

    // 状态卡只放"当前值"，历史时间统一收到运行记录里，避免同一信息出现两次。
    const statusStats = computed(() => [
      { label: '登录方式', value: status.value.login_type_title, icon: 'mdi-login-variant', color: 'primary' },
      { label: '浏览器', value: status.value.browser_mode_title, icon: 'mdi-web', color: 'primary' },
      { label: 'Cookie 数量', value: `${status.value.cookie_count ?? 0} 个`, icon: 'mdi-counter', color: status.value.has_cookie ? 'success' : 'grey' },
      { label: '检测周期', value: humanizeCron(status.value.check_cron), icon: 'mdi-clock-outline', color: 'primary' },
    ])

    // 运行记录：合并原先「近期结果」与「Cookie 管理」的重复项，只保留一份。
    const timeline = computed(() => [
      { label: '最近登录', value: status.value.last_run, icon: 'mdi-history', color: 'primary' },
      { label: '最近检测', value: status.value.last_check, icon: 'mdi-clock-check-outline', color: 'primary' },
      { label: '检测结果', value: status.value.last_check_status, icon: 'mdi-shield-check-outline', color: status.value.last_check_status ? 'success' : 'grey' },
      { label: '最近同步', value: status.value.last_openlist_sync, icon: 'mdi-calendar-clock', color: 'primary' },
      { label: '同步结果', value: status.value.last_openlist_sync_status, icon: 'mdi-cloud-sync-outline', color: status.value.last_openlist_sync_status ? 'info' : 'grey' },
    ])

    // 底部把空白换成一句有用的话，而不是留一大片空。
    const tipText = computed(() => {
      if (status.value.running) return '二维码有效期较短，请尽快用微信或 QQ 扫码。'
      if (!status.value.has_cookie) return '扫码成功后会自动保存 Cookie，并按配置同步到 OpenList。'
      if (status.value.enabled) return '插件已启用，会按检测周期自动检查 Cookie 是否失效。'
      return '插件当前未启用，仅手动操作可用；到「设置」里可以开启。'
    })

    // 未生成二维码时的三步引导，把左侧空白变成有用的说明
    const steps = [
      { icon: 'mdi-numeric-1-circle-outline', title: '启动扫码', desc: '点击上方按钮，自动打开微云登录页并生成二维码。' },
      { icon: 'mdi-numeric-2-circle-outline', title: '扫码登录', desc: '用微信或 QQ 扫描二维码，二维码有时效，请尽快完成。' },
      { icon: 'mdi-numeric-3-circle-outline', title: '自动保存', desc: '登录成功后自动保存 Cookie，并按配置同步到 OpenList。' },
    ]

    function clearMessage() {
      if (messageTimer) {
        clearTimeout(messageTimer)
        messageTimer = null
      }
      message.value = ''
    }

    function showMessage(text, delay = 4000) {
      clearMessage()
      message.value = text
      messageTimer = setTimeout(() => {
        message.value = ''
        messageTimer = null
      }, delay)
    }

    async function load(silent = false) {
      if (!silent) loading.value = true
      error.value = ''
      try {
        status.value = (await getPluginApi(props.api, 'status')) || {}
      } catch (err) {
        error.value = '加载状态失败：' + (err?.message || err)
      } finally {
        loading.value = false
      }
    }

    async function action(path, ok) {
      busy.value = true
      error.value = ''
      clearMessage()
      try {
        const result = await postPluginApi(props.api, path)
        showMessage(result?.message || ok || '操作已提交')
        await load(true)
      } catch (err) {
        error.value = (ok || '操作') + '失败：' + (err?.message || err)
      } finally {
        busy.value = false
      }
    }

    function eventCopy(text) {
      if (typeof document === 'undefined' || !document.addEventListener) return false
      let wrote = false
      const listener = (event) => {
        event.preventDefault()
        if (event.clipboardData) {
          event.clipboardData.setData('text/plain', text)
          wrote = true
        }
      }
      document.addEventListener('copy', listener)
      let ok = false
      try {
        ok = document.execCommand('copy')
      } catch (err) {
        ok = false
      } finally {
        document.removeEventListener('copy', listener)
      }
      return ok && wrote
    }

    async function copyCookie() {
      let text = ''
      error.value = ''
      clearMessage()
      try {
        const latest = (await getPluginApi(props.api, 'cookie')) || {}
        status.value = {
          ...status.value,
          has_cookie: latest.has_cookie ?? status.value.has_cookie,
          cookie_length: latest.cookie_length ?? status.value.cookie_length,
        }
        const grant = await postPluginApi(props.api, 'request_cookie_reveal')
        const token = grant?.token
        if (!token) throw new Error(grant?.message || '未取得一次性授权')
        const revealed = await postPluginApi(props.api, 'reveal_cookie', { reveal_token: token })
        text = revealed?.cookie || ''
      } catch (err) {
        error.value = '读取 Cookie 失败：' + (err?.message || err)
        return
      }
      if (!text) {
        error.value = '当前没有可复制的 Cookie，请先扫码登录'
        return
      }
      const copiedByEvent = eventCopy(text)
      if (copiedByEvent) {
        showMessage(`Cookie 已复制到剪贴板（${text.length} 字符）`)
        return
      }
      try {
        if (navigator?.clipboard?.writeText && window.isSecureContext) {
          await navigator.clipboard.writeText(text)
          showMessage(`Cookie 已复制到剪贴板（${text.length} 字符）`)
          return
        }
      } catch (err) {
        /* 回退失败则走统一错误提示 */
      }
      error.value = '复制失败，请刷新页面后重试'
    }

    onMounted(() => {
      load()
      timer = setInterval(() => load(true), 3000)
    })

    onBeforeUnmount(() => {
      if (timer) clearInterval(timer)
      clearMessage()
    })

    return {
      loading,
      busy,
      error,
      message,
      status,
      qrcodeSrc,
      stateColor,
      stateText,
      statusStats,
      timeline,
      tipText,
      steps,
      clearMessage,
      load,
      action,
      copyCookie,
    }
  },
}
</script>

<style scoped>
.wy-page { padding: 4px 0; }
</style>
