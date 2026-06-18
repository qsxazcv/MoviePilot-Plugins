import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const { defineComponent, h, reactive, computed, watch, resolveComponent } = await importShared('vue');

const groups = [
  {
    key: 'primary',
    title: '常用设置',
    icon: 'mdi-qrcode-scan',
    desc: '先确认启用状态、登录方式和扫码等待时间；需要马上更新 Cookie 时打开一次运行。',
    fields: [
      ['switch', 'enabled', '启用插件', '关闭后命令和周期检测不再执行。'],
      ['switch', 'onlyonce', '保存后立即运行一次', '保存配置后启动一次扫码登录，执行后自动关闭。'],
      ['select', 'login_type', '登录方式', 'QQ 或微信扫码登录。', [{ title: 'QQ 扫码登录', value: 'qq' }, { title: '微信扫码登录', value: 'wechat' }]],
      ['number', 'timeout_seconds', '扫码超时秒数', '建议 180 秒，范围 30-600。'],
    ],
  },
  {
    key: 'runtime',
    title: '登录环境',
    icon: 'mdi-web',
    desc: '默认设置通常可直接使用；遇到登录页兼容、QQ 域 Cookie 或外部通知二维码问题时再调整。',
    fields: [
      ['select', 'browser_mode', '浏览器模式', '插件内置速度较快；兼容模式适合复杂登录页。', [{ title: '插件内置', value: 'playwright' }, { title: '兼容模式', value: 'cloakbrowser' }]],
      ['switch', 'headless', '无头浏览器', '开启后后台运行；关闭可用于排障。'],
      ['switch', 'include_qq_domain', '包含 QQ 域 Cookie', 'QQ 登录建议开启。'],
      ['text', 'login_url', '微云登录入口', '默认 https://www.weiyun.com/。'],
      ['text', 'qrcode_public_base_url', '二维码公网地址', '可选，用于企业微信等外部通知展示二维码。'],
    ],
  },
  {
    key: 'automation',
    title: '自动检测与通知',
    icon: 'mdi-shield-check-outline',
    desc: '控制 Cookie 周期检测、失效提醒和 MoviePilot 通知范围，适合长期无人值守。',
    fields: [
      ['switch', 'check_enabled', '启用周期检测', '按 Cron 定时检查 Cookie。'],
      ['text', 'check_cron', '检测 Cron', '默认 0 */6 * * *，每 6 小时检测一次。'],
      ['switch', 'check_onlyonce', '保存后立即检测一次', '执行后自动关闭。'],
      ['switch', 'check_notify', '失效时通知', 'Cookie 失效时提醒重新登录。'],
      ['switch', 'notify_enabled', '启用 MoviePilot 通知', '总通知开关。'],
      ['switch', 'notify_login_result', '通知登录结果', '扫码开始、成功、失败等消息。'],
      ['switch', 'notify_openlist_result', '通知 OpenList 同步结果', '同步成功或失败时发送通知。'],
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
      ['last_openlist_sync_status', '同步结果', 'mdi-cloud-sync-outline', 'info'],
      ['last_openlist_sync', '同步时间', 'mdi-calendar-clock', 'info'],
    ],
  },
];

const wideModels = new Set(['login_url', 'qrcode_public_base_url', 'openlist_url', 'openlist_token', 'last_openlist_sync_status']);

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
    const VBtn = C('VBtn');
    const VAlert = C('VAlert');
    const VChip = C('VChip');

    const form = reactive({});
    const openSections = reactive({ primary: true });

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

    function archiveItem(def) {
      const [model, label, icon, color = 'primary'] = def;
      const value = model === 'last_cookie_count' ? `${form[model] ?? 0} 个` : form[model];
      return h('div', { class: 'wy-archive-item' }, [
        h(VIcon, { icon, color, size: '18' }),
        h('div', { class: 'wy-archive-body' }, [
          h('div', { class: 'wy-archive-label' }, label),
          h('div', { class: 'wy-archive-value' }, value || '—'),
        ]),
      ]);
    }

    function field(def, compactSwitch = false) {
      const [type, model, label, hint, items] = def;
      if (type === 'switch') {
        if (compactSwitch) {
          return h('div', { class: 'wy-switch-tile' }, [
            h('div', { class: 'wy-switch-copy' }, [
              h('div', { class: 'wy-switch-title' }, label),
              hint && h('div', { class: 'wy-switch-hint' }, hint),
            ]),
            h(VSwitch, {
              modelValue: !!form[model],
              color: 'primary',
              density: 'compact',
              hideDetails: true,
              inset: true,
              'onUpdate:modelValue': (value) => form[model] = value,
            }),
          ]);
        }
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

    function section(group, index) {
      const switchFields = group.compact ? [] : group.fields.filter((def) => def[0] === 'switch');
      const inputFields = group.compact ? [] : group.fields.filter((def) => def[0] !== 'switch');
      return h('details', {
        class: ['wy-section', `wy-section--${group.key}`],
        open: !!openSections[group.key],
        onToggle: (event) => openSections[group.key] = event.target.open,
      }, [
        h('summary', { class: 'wy-section-head' }, [
          h('div', { class: 'wy-section-title' }, [h(VIcon, { icon: group.icon, size: '18' }), h('span', group.title)]),
          h('div', { class: 'wy-section-desc' }, group.desc),
          h(VIcon, { class: 'wy-section-chevron', icon: 'mdi-chevron-down', size: '20' }),
        ]),
        h('div', { class: 'wy-section-body' }, [
          group.alert && h(VAlert, { type: 'warning', variant: 'tonal', density: 'compact', class: 'mb-3' }, () => group.alert),
          group.compact && h('div', { class: 'wy-archive-grid' }, group.fields.map(archiveItem)),
          switchFields.length > 0 && h('div', { class: 'wy-switch-grid' }, switchFields.map((def) => field(def, true))),
          inputFields.length > 0 && h(VRow, { dense: true, class: 'wy-field-grid' }, () => inputFields.map((def) => h(VCol, {
            cols: 12,
            md: wideModels.has(def[1]) ? 12 : 6,
          }, () => field(def)))),
        ]),
      ]);
    }

    return () => h('div', { class: 'wy-config' }, [
      h(VCard, { class: 'wy-console-card', elevation: 0 }, () => [
        h('div', { class: 'wy-console-hero' }, [
          h('div', [
            h('div', { class: 'text-h6' }, '微云 Cookie 助手 · 设置'),
            h('div', { class: 'wy-hint' }, `按使用频率分区：先配置扫码登录，再按需调整检测通知和 OpenList。最近状态：${form.last_status || '未运行'}`),
          ]),
          h('div', { class: 'wy-hero-actions' }, [
            h(VChip, { color: form.enabled ? 'success' : 'default', variant: 'tonal', size: 'small' }, () => form.enabled ? '已启用' : '未启用'),
            h(VBtn, { size: 'small', color: 'primary', prependIcon: 'mdi-content-save-outline', onClick: save }, () => '保存设置'),
            h(VBtn, { size: 'small', variant: 'text', prependIcon: 'mdi-close', onClick: () => emit('close') }, () => '关闭'),
          ]),
        ]),
        h('div', { class: 'wy-console-stats' }, [
          stat('登录方式', loginTypeText.value, 'mdi-login-variant'),
          stat('浏览器', browserModeText.value, 'mdi-web'),
          stat('检测周期', form.check_cron, 'mdi-clock-outline'),
          stat('Cookie', `${cookieCountText.value} 个`, 'mdi-cookie-outline', Number(form.last_cookie_count || 0) > 0 ? 'success' : 'grey'),
          stat('OpenList', form.openlist_enabled ? '已启用' : '未启用', 'mdi-cloud-sync-outline', form.openlist_enabled ? 'info' : 'grey'),
        ]),
        h('div', { class: 'wy-settings-sheet' }, groups.map(section)),
      ]),
    ]);
  },
});
