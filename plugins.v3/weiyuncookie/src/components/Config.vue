<template>
  <div class="wy-config">
    <VCard class="wy-console-card" :elevation="0">
      <!-- 顶部：标题 + 启用状态 + 关闭 -->
      <div class="wy-console-hero">
        <div>
          <div class="text-h6">微云 Cookie 助手 · 设置</div>
          <div class="wy-hint">
            扫码登录分成两步：先在上方打开「启用插件」，再勾选「保存后立即运行一次」并保存。最近状态：{{ form.last_status || '未运行' }}
          </div>
        </div>
        <div class="wy-hero-actions">
          <VChip :color="form.enabled ? 'success' : 'default'" variant="tonal" size="small">
            {{ form.enabled ? '已启用' : '未启用' }}
          </VChip>
          <VBtn size="small" variant="text" prepend-icon="mdi-close" @click="$emit('close')">关闭</VBtn>
        </div>
      </div>

      <!-- 状态卡：全部用人话，不直接抛 cron 原文 -->
      <div class="wy-console-stats">
        <div v-for="item in stats" :key="item.label" class="wy-console-stat">
          <div class="wy-console-label">
            <VIcon :icon="item.icon" size="15" :color="item.color" class="mr-1" />{{ item.label }}
          </div>
          <div class="wy-console-value">{{ item.value || '—' }}</div>
        </div>
      </div>

      <!-- 常驻操作栏：高频动作不隐藏在折叠区里 -->
      <div class="wy-quick-bar">
        <div class="wy-quick-main">
          <div class="wy-quick-switch">
            <div class="wy-quick-copy">
              <div class="wy-switch-title">启用插件</div>
              <div class="wy-switch-hint">关闭后命令与周期检测停止。</div>
            </div>
            <VSwitch v-model="form.enabled" color="primary" density="comfortable" hide-details />
          </div>
          <div class="wy-quick-switch">
            <div class="wy-quick-copy">
              <div class="wy-switch-title">保存后立即运行一次</div>
              <div class="wy-switch-hint">保存后跑一次扫码登录，结束后自动关闭。</div>
            </div>
            <VSwitch v-model="form.onlyonce" color="primary" density="comfortable" hide-details />
          </div>
        </div>
        <div class="wy-quick-actions">
          <VBtn color="primary" prepend-icon="mdi-content-save-outline" :loading="saving" @click="save">保存设置</VBtn>
          <div class="wy-quick-hint">{{ savedHint }}</div>
        </div>
      </div>

      <!-- 设置区：只渲染低频分区，primary 已提到上方常驻栏 -->
      <div class="wy-settings-sheet">
        <details
          v-for="group in collapsedGroups"
          :key="group.key"
          class="wy-section"
          :class="`wy-section--${group.key}`"
          :open="!!openSections[group.key]"
          @toggle="onToggle(group, $event)"
        >
          <summary class="wy-section-head">
            <div class="wy-section-copy">
              <div class="wy-section-title">
                <VIcon :icon="group.icon" size="18" /><span>{{ group.title }}</span>
              </div>
              <div class="wy-section-desc">{{ group.desc }}</div>
            </div>
            <VIcon class="wy-section-chevron" icon="mdi-chevron-down" size="20" />
          </summary>
          <div class="wy-section-body">
            <VAlert v-if="group.alert" type="warning" variant="tonal" density="compact" class="mb-3">
              {{ group.alert }}
            </VAlert>

            <div v-if="group.compact" class="wy-archive-grid">
              <div v-for="def in group.fields" :key="def[0]" class="wy-archive-item">
                <VIcon :icon="def[2]" :color="def[3] || 'primary'" size="18" />
                <div class="wy-archive-body">
                  <div class="wy-archive-label">{{ def[1] }}</div>
                  <div class="wy-archive-value">{{ archiveValue(def[0]) }}</div>
                </div>
              </div>
            </div>

            <template v-else>
              <div v-if="switchFields(group).length" class="wy-switch-grid">
                <div v-for="def in switchFields(group)" :key="def[1]" class="wy-switch-tile">
                  <div class="wy-switch-copy">
                    <div class="wy-switch-title">{{ def[2] }}</div>
                    <div v-if="def[3]" class="wy-switch-hint">{{ def[3] }}</div>
                  </div>
                  <VSwitch v-model="form[def[1]]" color="primary" density="compact" hide-details inset />
                </div>
              </div>

              <VRow v-if="inputFields(group).length" dense class="wy-field-grid">
                <VCol
                  v-for="def in inputFields(group)"
                  :key="def[1]"
                  cols="12"
                  :md="wideModels.has(def[1]) ? 12 : 6"
                >
                  <VSelect
                    v-if="def[0] === 'select'"
                    v-model="form[def[1]]"
                    :label="def[2]"
                    :items="def[4]"
                    variant="outlined"
                    density="comfortable"
                    :hint="def[3]"
                    persistent-hint
                  />
                  <VTextField
                    v-else
                    v-model="form[def[1]]"
                    :label="def[2]"
                    variant="outlined"
                    density="comfortable"
                    :hint="def[3]"
                    persistent-hint
                    :type="def[0] === 'password' ? 'password' : 'text'"
                    :clearable="def[0] === 'text' || def[0] === 'password'"
                    @update:model-value="(v) => onInput(def, v)"
                  />
                </VCol>
              </VRow>
            </template>
          </div>
        </details>
      </div>
    </VCard>
  </div>
</template>

<script>
import { reactive, ref, computed, watch } from 'vue'
import '../styles/config.css'

// 配置分组定义：只描述数据，渲染交给模板，避免手改编译产物。
export const CONFIG_GROUPS = [
  {
    key: 'primary',
    title: '常用设置',
    icon: 'mdi-qrcode-scan',
    desc: '先设置启用状态、登录方式和扫码等待时间；想立刻更新 Cookie，勾选「保存后立即运行一次」再保存。',
    fields: [
      ['switch', 'enabled', '启用插件', '关闭后命令与周期检测停止。'],
      ['switch', 'onlyonce', '保存后立即运行一次', '保存后跑一次扫码登录，结束后自动关闭。'],
      ['select', 'login_type', '登录方式', '选择 QQ 或微信扫码。', [
        { title: 'QQ 扫码登录', value: 'qq' },
        { title: '微信扫码登录', value: 'wechat' },
      ]],
      ['number', 'timeout_seconds', '扫码超时秒数', '等待扫码的时长，范围 30-600，建议 180。'],
    ],
  },
  {
    key: 'runtime',
    title: '登录环境',
    icon: 'mdi-web',
    desc: '默认即可用；仅当登录页不兼容、需要 QQ 域 Cookie 或外部通知二维码时才调整。',
    fields: [
      ['select', 'browser_mode', '浏览器模式', '登录统一使用 MP CloakBrowser，兼容性最好。', [
        { title: 'CloakBrowser', value: 'cloakbrowser' },
      ]],
      ['switch', 'headless', '无头浏览器', '开启后台运行；排障时可关闭。'],
      ['switch', 'include_qq_domain', '包含 QQ 域 Cookie', '应用 QQ 登录时建议开启。'],
      ['text', 'login_url', '微云登录入口', '默认 https://www.weiyun.com/。'],
      ['text', 'qrcode_public_base_url', '二维码公网地址', '可选，供企业微信等外部通知展示二维码。'],
    ],
  },
  {
    key: 'automation',
    title: '自动检测与通知',
    icon: 'mdi-shield-check-outline',
    desc: '定期检查 Cookie 是否失效并推送提醒，适合长期无人值守。',
    fields: [
      ['switch', 'check_enabled', '启用周期检测', '按 Cron 定时检查 Cookie。'],
      ['text', 'check_cron', '检测 Cron', '默认 0 */6 * * *，即每 6 小时一次。'],
      ['switch', 'check_onlyonce', '保存后立即检测一次', '执行后自动关闭。'],
      ['switch', 'check_notify', '失效时通知', 'Cookie 失效时提醒重新登录。'],
      ['switch', 'notify_enabled', '启用 MoviePilot 通知', '总通知开关，关闭后全部不推送。'],
      ['switch', 'notify_login_result', '通知登录结果', '登录完成后推送一条摘要（含 Cookie 数量与同步结果）。'],
      ['switch', 'notify_openlist_result', '通知 OpenList 同步结果', '仅用于手动同步；登录时的同步结果已并入登录摘要。'],
    ],
  },
  {
    key: 'openlist',
    title: 'OpenList 同步',
    icon: 'mdi-cloud-sync-outline',
    desc: '填写 OpenList 地址、Token 和存储 ID 后，可把最新 Cookie 写入腾讯微云存储配置。',
    alert: 'Token 属于敏感配置，请勿在日志、截图或 issue 中公开。',
    fields: [
      ['switch', 'openlist_enabled', '启用 OpenList 同步', '开启后可手动或自动同步 Cookie。'],
      ['switch', 'openlist_auto_sync', '扫码成功后自动同步', '登录成功后立即写入 OpenList。'],
      ['switch', 'openlist_sync_after_relogin', '失效重登后同步', '检测失效后重新扫码成功时自动同步。'],
      ['switch', 'openlist_sync_onlyonce', '保存后立即同步一次', '执行后自动关闭。'],
      ['text', 'openlist_url', 'OpenList 地址', '例如 http://192.168.5.100:5244。'],
      ['password', 'openlist_token', 'OpenList Token', '保存后用于调用 OpenList 管理接口。'],
      ['number', 'openlist_storage_id', 'OpenList 存储 ID', '腾讯微云存储对应 ID。'],
    ],
  },
  {
    key: 'archive',
    title: '运行档案',
    icon: 'mdi-book-open-page-variant-outline',
    desc: '只读状态摘要，用来确认最近登录、检测、同步结果和 Cookie 数量。',
    compact: true,
    fields: [
      ['last_status', '最近状态', 'mdi-list-status', 'primary'],
      ['last_run', '最近登录', 'mdi-history', 'primary'],
      ['last_cookie_count', 'Cookie 数量', 'mdi-cookie-outline', 'success'],
      ['last_check_status', '检测结果', 'mdi-shield-check-outline', 'success'],
      ['last_check', '最近检测', 'mdi-clock-check-outline', 'primary'],
      ['last_openlist_sync', '最近同步', 'mdi-cloud-upload-outline', 'info'],
      ['last_openlist_sync_status', '同步结果', 'mdi-cloud-check-outline', 'info'],
    ],
  },
]

/**
 * 把 cron 表达式翻成一句人话，避免顶栏直接甩出六段式原文。
 */
export function humanizeCron(expr) {
  const raw = String(expr || '').trim()
  if (!raw) return '未启用'
  if (raw === '0 */6 * * *') return '每 6 小时'
  const hourly = raw.match(/^0 \*\/(\d+) \* \* \*$/)
  if (hourly) return `每 ${hourly[1]} 小时`
  const everyMinutes = raw.match(/^\*\/(\d+) \* \* \* \*$/)
  if (everyMinutes) return `每 ${everyMinutes[1]} 分钟`
  const daily = raw.match(/^(\d+) (\d+) \* \* \*$/)
  if (daily) return `每天 ${String(daily[2]).padStart(2, '0')}:${String(daily[1]).padStart(2, '0')}`
  return raw
}

export default {
  name: 'Config',
  props: {
    initialConfig: { type: Object, default: () => ({}) },
    api: { type: [Object, Function], default: null },
  },
  emits: ['save', 'close', 'switch'],
  setup(props, { emit }) {
    const form = reactive({})
    const openSections = reactive({ primary: true })
    const saving = ref(false)
    const savedHint = ref('')
    let savedTimer = null

    watch(
      () => props.initialConfig,
      (value) => {
        Object.keys(form).forEach((key) => delete form[key])
        Object.assign(form, value || {})
      },
      { immediate: true, deep: true },
    )

    const wideModels = new Set(['login_url', 'qrcode_public_base_url', 'openlist_url', 'openlist_token', 'check_cron'])

    const collapsedGroups = computed(() => CONFIG_GROUPS.filter((group) => group.key !== 'primary'))

    const checkCycleText = computed(() => humanizeCron(form.check_cron))

    // Cookie 卡片同时体现"有没有"和"数量"，失效时不再只显示一个 0。
    const cookieState = computed(() => {
      const count = Number(form.last_cookie_count ?? 0)
      const status = String(form.last_status || '')
      if (!count) return { text: '未获取', color: 'warning' }
      if (status.indexOf('失败') >= 0) return { text: `可能失效（${count} 项）`, color: 'warning' }
      return { text: `${count} 项`, color: 'success' }
    })

    const stats = computed(() => [
      { label: '登录方式', value: form.login_type === 'wechat' ? '微信扫码' : 'QQ 扫码', icon: 'mdi-login-variant', color: 'primary' },
      { label: '浏览器', value: 'CloakBrowser', icon: 'mdi-web', color: 'primary' },
      { label: '检测周期', value: checkCycleText.value, icon: 'mdi-clock-outline', color: 'primary' },
      { label: 'Cookie', value: cookieState.value.text, icon: 'mdi-cookie-outline', color: cookieState.value.color },
      {
        label: 'OpenList',
        value: form.openlist_enabled ? '已启用' : '未启用',
        icon: 'mdi-cloud-sync-outline',
        color: form.openlist_enabled ? 'info' : 'grey',
      },
    ])

    function switchFields(group) {
      return group.compact ? [] : group.fields.filter((def) => def[0] === 'switch')
    }

    function inputFields(group) {
      return group.compact ? [] : group.fields.filter((def) => def[0] !== 'switch')
    }

    function archiveValue(model) {
      if (model === 'last_cookie_count') return `${form[model] ?? 0} 个`
      return form[model] || '—'
    }

    function onInput(def, value) {
      form[def[1]] = def[0] === 'number' ? Number(value || 0) : value
    }

    function onToggle(group, event) {
      openSections[group.key] = event.target.open
    }

    function save() {
      emit('save', { ...form })
      // 保存后给出明确回馈：原来点完几乎没有任何反应，用户不知道成没成。
      saving.value = true
      savedHint.value = '正在保存…'
      if (savedTimer) clearTimeout(savedTimer)
      savedTimer = setTimeout(() => {
        saving.value = false
        savedHint.value = '已提交保存，配置将在插件重载后生效。'
      }, 700)
    }

    return {
      form,
      openSections,
      saving,
      savedHint,
      wideModels,
      collapsedGroups,
      stats,
      switchFields,
      inputFields,
      archiveValue,
      onInput,
      onToggle,
      save,
    }
  },
}
</script>

<style scoped>
.wy-config { padding: 4px 0; }
</style>
