import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const { defineComponent, h, reactive, computed, watch, resolveComponent } = await importShared('vue');

const sectionMeta = [
  { key: 'login', title: '扫码登录', icon: 'mdi-qrcode-scan', color: 'primary', desc: 'QQ / 微信扫码、浏览器模式与运行参数。' },
  { key: 'notify', title: '通知策略', icon: 'mdi-bell-outline', color: 'info', desc: '登录结果、检测提醒与同步通知。' },
  { key: 'check', title: '有效性检测', icon: 'mdi-shield-check-outline', color: 'success', desc: '按 Cron 周期检查 Cookie 可用性。' },
  { key: 'openlist', title: 'OpenList 同步', icon: 'mdi-cloud-sync-outline', color: 'cyan', desc: '将最新 Cookie 写入腾讯微云存储。' },
  { key: 'status', title: '运行档案', icon: 'mdi-book-open-page-variant-outline', color: 'deep-purple', desc: '最近登录、检测、同步与完整 Cookie。' },
];

const fieldDefs = {
  login: [
    ['switch', 'enabled', '启用插件', '关闭后命令和周期检测不再执行。'],
    ['switch', 'onlyonce', '保存后立即运行一次', '保存配置后启动一次扫码登录，执行后自动关闭。'],
    ['select', 'login_type', '登录方式', 'QQ 或微信扫码登录。', [{ title: 'QQ 扫码登录', value: 'qq' }, { title: '微信扫码登录', value: 'wechat' }]],
    ['select', 'browser_mode', '浏览器模式', '插件内置速度较快；兼容模式适合复杂登录页。', [{ title: '插件内置', value: 'playwright' }, { title: '兼容模式', value: 'cloakbrowser' }]],
    ['switch', 'headless', '无头浏览器', '开启后后台运行；关闭可用于排障。'],
    ['number', 'timeout_seconds', '扫码超时秒数', '建议 180 秒，范围 30-600。'],
    ['switch', 'include_qq_domain', '包含 QQ 域 Cookie', 'QQ 登录建议开启。'],
    ['text', 'login_url', '微云登录入口', '默认 https://www.weiyun.com/。'],
    ['text', 'qrcode_public_base_url', '二维码公网地址', '可选，用于企业微信等外部通知展示二维码。'],
  ],
  notify: [
    ['switch', 'notify_enabled', '启用 MoviePilot 通知', '总通知开关。'],
    ['switch', 'notify_login_result', '通知登录结果', '扫码开始、成功、失败等消息。'],
    ['switch', 'notify_openlist_result', '通知 OpenList 同步结果', '同步成功或失败时发送通知。'],
  ],
  check: [
    ['switch', 'check_enabled', '启用周期检测', '按 Cron 定时检查 Cookie。'],
    ['switch', 'check_onlyonce', '保存后立即检测一次', '执行后自动关闭。'],
    ['switch', 'check_notify', '失效时通知', 'Cookie 失效时提醒重新登录。'],
    ['text', 'check_cron', '检测 Cron', '默认 0 */6 * * *，每 6 小时检测一次。'],
  ],
  openlist: [
    ['switch', 'openlist_enabled', '启用 OpenList 同步', '开启后可手动或自动同步 Cookie。'],
    ['switch', 'openlist_auto_sync', '扫码成功后自动同步', '登录成功后立即写入 OpenList。'],
    ['switch', 'openlist_sync_after_relogin', '失效重登后同步', '检测失效后重新扫码成功时自动同步。'],
    ['switch', 'openlist_sync_onlyonce', '保存后立即同步一次', '执行后自动关闭。'],
    ['text', 'openlist_url', 'OpenList 地址', '例如 http://192.168.5.100:5244。'],
    ['password', 'openlist_token', 'OpenList Token', '保存后用于调用 OpenList 管理接口。'],
    ['number', 'openlist_storage_id', 'OpenList 存储 ID', '腾讯微云存储对应 ID。'],
  ],
  status: [
    ['readonly', 'last_status', '最近状态', ''],
    ['readonly', 'last_run', '最近登录时间', ''],
    ['readonly', 'last_cookie_count', 'Cookie 数量', ''],
    ['readonly', 'last_check', '最近检测时间', ''],
    ['readonly', 'last_check_status', '最近检测结果', ''],
    ['readonly', 'last_openlist_sync', '最近同步时间', ''],
    ['readonly', 'last_openlist_sync_status', '最近同步结果', ''],
    ['textarea', 'cookie_full', '完整 Cookie', '只读展示，便于手动复制。'],
  ],
};

const wideModels = new Set(['login_url', 'qrcode_public_base_url', 'openlist_url', 'openlist_token', 'cookie_full']);

export default defineComponent({
  name: 'Config',
  props: {
    initialConfig: { type: Object, default: () => ({}) },
    api: { type: [Object, Function], default: null },
  },
  emits: ['save', 'close', 'switch'],
  setup(props, { emit }) {
    const C = (name) => resolveComponent(name);
    const VCard = C('VCard');
    const VIcon = C('VIcon');
    const VRow = C('VRow');
    const VCol = C('VCol');
    const VSwitch = C('VSwitch');
    const VTextField = C('VTextField');
    const VSelect = C('VSelect');
    const VTextarea = C('VTextarea');
    const VBtn = C('VBtn');
    const VAlert = C('VAlert');
    const VChip = C('VChip');

    const form = reactive({});

    watch(() => props.initialConfig, (value) => {
      Object.keys(form).forEach((key) => delete form[key]);
      Object.assign(form, value || {});
    }, { immediate: true, deep: true });

    const loginTypeText = computed(() => form.login_type === 'wechat' ? '微信扫码' : 'QQ 扫码');
    const browserModeText = computed(() => form.browser_mode === 'cloakbrowser' ? '兼容模式' : '插件内置');
    const cookieCountText = computed(() => String(form.last_cookie_count ?? 0));

    function save() {
      emit('save', { ...form });
    }

    function stat(label, value, icon, color = 'primary') {
      return h('div', { class: 'wy-console-stat' }, [
        h('div', { class: 'wy-console-label' }, [h(VIcon, { icon, size: '15', color, class: 'mr-1' }), label]),
        h('div', { class: 'wy-console-value' }, value || '—'),
      ]);
    }

    function field(def) {
      const [type, model, label, hint, items] = def;
      if (type === 'switch') {
        return h(VSwitch, {
          modelValue: !!form[model],
          label,
          color: 'primary',
          density: 'comfortable',
          hint,
          'persistent-hint': !!hint,
          'onUpdate:modelValue': (value) => form[model] = value,
        });
      }
      if (type === 'select') {
        return h(VSelect, {
          modelValue: form[model],
          label,
          items,
          variant: 'outlined',
          density: 'comfortable',
          hint,
          'persistent-hint': !!hint,
          'onUpdate:modelValue': (value) => form[model] = value,
        });
      }
      if (type === 'textarea') {
        return h(VTextarea, {
          modelValue: form[model] || '',
          label,
          readonly: true,
          rows: 8,
          'auto-grow': false,
          variant: 'outlined',
          density: 'comfortable',
          hint,
          'persistent-hint': !!hint,
          class: 'wy-cookie-textarea',
        });
      }
      return h(VTextField, {
        modelValue: form[model] ?? '',
        label,
        variant: 'outlined',
        density: 'comfortable',
        hint,
        'persistent-hint': !!hint,
        readonly: type === 'readonly',
        disabled: type === 'readonly',
        type: type === 'password' ? 'password' : type === 'number' ? 'number' : 'text',
        clearable: type === 'text' || type === 'password',
        'onUpdate:modelValue': (value) => form[model] = type === 'number' ? Number(value || 0) : value,
      });
    }

    function sectionCard(section) {
      const enabledMap = {
        login: !!form.enabled,
        notify: !!form.notify_enabled,
        check: !!form.check_enabled,
        openlist: !!form.openlist_enabled,
        status: !!form.cookie_full,
      };
      const stateText = section.key === 'status'
        ? (form.cookie_full ? `${cookieCountText.value} 个 Cookie` : '暂无 Cookie')
        : (enabledMap[section.key] ? '已开启' : '未开启');
      return h('div', { class: 'wy-feature-card' }, [
        h('div', { class: 'wy-feature-head' }, [
          h('div', [h(VIcon, { icon: section.icon, color: section.color, size: '18', class: 'mr-1' }), h('span', section.title)]),
          h(VChip, { size: 'x-small', variant: 'tonal', color: enabledMap[section.key] ? 'success' : 'default' }, () => stateText),
        ]),
        h('div', { class: 'wy-feature-main' }, section.desc),
        h('div', { class: 'wy-feature-sub' }, section.key === 'login' ? `${loginTypeText.value} · ${browserModeText.value}` : fieldDefs[section.key].length + ' 项配置'),
      ]);
    }

    function settingSection(section) {
      const note = section.key === 'openlist'
        ? 'Token 属于敏感配置，请勿在日志、截图或 issue 中公开。'
        : section.key === 'status'
          ? '运行档案由插件回填，保存设置不会清理现有 Cookie。'
          : '';
      return h(VCard, { variant: 'outlined', class: 'wy-setting-card' }, () => [
        h('div', { class: 'wy-setting-title' }, [h(VIcon, { icon: section.icon, size: '18' }), section.title]),
        note && h(VAlert, { type: section.key === 'openlist' ? 'warning' : 'info', variant: 'tonal', density: 'compact', class: 'mb-3' }, () => note),
        h(VRow, { dense: true }, () => fieldDefs[section.key].map((def) => h(VCol, {
          cols: 12,
          md: def[0] === 'textarea' || wideModels.has(def[1]) ? 12 : 6,
        }, () => field(def)))),
      ]);
    }

    return () => h('div', { class: 'wy-config' }, [
      h(VCard, { class: 'wy-console-card', elevation: 0 }, () => [
        h('div', { class: 'wy-console-hero' }, [
          h('div', [
            h('div', { class: 'text-h6' }, '微云 Cookie 助手 · 控制台'),
            h('div', { class: 'wy-hint' }, `登录方式：${loginTypeText.value}，检测周期：${form.check_cron || '未配置'}，最近状态：${form.last_status || '未运行'}`),
          ]),
          h('div', { class: 'wy-hero-actions' }, [
            h(VChip, { color: form.enabled ? 'success' : 'default', variant: 'tonal', size: 'small' }, () => form.enabled ? '已启用' : '未启用'),
            h(VBtn, { size: 'small', color: 'primary', prependIcon: 'mdi-content-save-outline', onClick: save }, () => '保存设置'),
            h(VBtn, { size: 'small', variant: 'text', prependIcon: 'mdi-close', onClick: () => emit('close') }, () => '关闭'),
          ]),
        ]),
        h('div', { class: 'wy-console-stats' }, [
          stat('插件状态', form.enabled ? '已启用' : '未启用', 'mdi-power', form.enabled ? 'success' : 'grey'),
          stat('登录方式', loginTypeText.value, 'mdi-login-variant'),
          stat('浏览器模式', browserModeText.value, 'mdi-web'),
          stat('检测周期', form.check_cron, 'mdi-clock-outline'),
          stat('Cookie 数量', cookieCountText.value, 'mdi-cookie-outline'),
          stat('最近状态', form.last_status, 'mdi-check-decagram-outline'),
        ]),
        h('div', { class: 'wy-feature-grid' }, sectionMeta.map(sectionCard)),
        h('div', { class: 'wy-data-hint' }, [h(VIcon, { icon: 'mdi-shield-lock-outline', size: '16' }), '界面只重排配置与展示，不改变现有 QQ / 微信扫码、Cookie 提取、检测和 OpenList 同步逻辑。']),
        h('div', { class: 'wy-form-grid' }, sectionMeta.map(settingSection)),
      ]),
    ]);
  },
});
