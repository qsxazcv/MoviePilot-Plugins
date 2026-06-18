import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-weiyuncookie.js';

const { defineComponent, h, ref, computed, onMounted, onBeforeUnmount, resolveComponent } = await importShared('vue');

export default defineComponent({
  name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(props, { emit }) {
    const C = (name) => resolveComponent(name);
    const VToolbar = C('VToolbar');
    const VToolbarTitle = C('VToolbarTitle');
    const VBtn = C('VBtn');
    const VIcon = C('VIcon');
    const VAlert = C('VAlert');
    const VCard = C('VCard');
    const VCardText = C('VCardText');
    const VRow = C('VRow');
    const VCol = C('VCol');
    const VProgressCircular = C('VProgressCircular');
    const VChip = C('VChip');
    const VDivider = C('VDivider');

    const loading = ref(false);
    const busy = ref(false);
    const error = ref('');
    const message = ref('');
    const status = ref({});
    let timer = null;

    const qrcodeSrc = computed(() => status.value?.has_qrcode && status.value?.qrcode ? status.value.qrcode : '');
    const stateColor = computed(() => status.value.running ? 'warning' : status.value.has_cookie ? 'success' : 'default');
    const stateText = computed(() => status.value.running ? '扫码进行中' : status.value.has_cookie ? 'Cookie 已保存' : '等待登录');

    async function load(silent = false) {
      if (!silent) loading.value = true;
      error.value = '';
      try {
        status.value = await getPluginApi(props.api, 'status') || {};
      } catch (err) {
        error.value = '加载状态失败：' + (err?.message || err);
      } finally {
        loading.value = false;
      }
    }

    async function action(path, ok) {
      busy.value = true;
      error.value = '';
      message.value = '';
      try {
        const result = await postPluginApi(props.api, path);
        message.value = result?.message || ok || '操作已提交';
        await load(true);
      } catch (err) {
        error.value = (ok || '操作') + '失败：' + (err?.message || err);
      } finally {
        busy.value = false;
      }
    }

    async function copyCookie() {
      try {
        await navigator.clipboard.writeText(status.value.cookie || '');
        message.value = 'Cookie 已复制到剪贴板';
      } catch (err) {
        error.value = '复制失败，请稍后重试';
      }
    }

    function stat(label, value, icon, color = 'primary') {
      return h('div', { class: 'wy-status-item' }, [
        h('div', { class: 'wy-status-label' }, [h(VIcon, { icon, size: '15', class: 'mr-1', color }), label]),
        h('div', { class: 'wy-status-value' }, value || '—'),
      ]);
    }

    function timeline(label, value, icon, color = 'primary') {
      return h('div', { class: 'wy-timeline-row' }, [
        h(VIcon, { icon, color, size: '18' }),
        h('div', { class: 'wy-timeline-body' }, [
          h('div', { class: 'wy-timeline-label' }, label),
          h('div', { class: 'wy-timeline-value' }, value || '—'),
        ]),
      ]);
    }

    function meta(label, value) {
      return h('div', { class: 'wy-cookie-meta-row' }, [
        h('span', { class: 'wy-cookie-meta-label' }, label),
        h('span', { class: 'wy-cookie-meta-value' }, value || '—'),
      ]);
    }

    onMounted(() => {
      load();
      timer = setInterval(() => load(true), 3000);
    });

    onBeforeUnmount(() => timer && clearInterval(timer));

    return () => h('div', { class: 'wy-page' }, [
      h(VToolbar, { class: 'wy-toolbar', density: 'comfortable' }, () => [
        h(VToolbarTitle, '微云 Cookie 助手'),
        h(VBtn, { icon: 'mdi-play-circle-outline', variant: 'text', title: '启动扫码登录', loading: busy.value, onClick: () => action('start_login', '已启动微云扫码登录') }),
        h(VBtn, { icon: 'mdi-shield-check-outline', variant: 'text', title: '立即检测', loading: busy.value, onClick: () => action('check_cookie', '检测完成') }),
        h(VBtn, { icon: 'mdi-cloud-sync-outline', variant: 'text', title: '同步 OpenList', loading: busy.value, onClick: () => action('sync_openlist', '同步完成') }),
        h(VBtn, { icon: 'mdi-refresh', variant: 'text', title: '刷新', loading: loading.value, onClick: () => load() }),
        h(VBtn, { icon: 'mdi-cog-outline', variant: 'text', title: '设置', onClick: () => emit('switch') }),
        h(VBtn, { icon: 'mdi-close', variant: 'text', title: '关闭', onClick: () => emit('close') }),
      ]),
      h('div', { class: 'wy-page-wrap' }, [
        error.value && h(VAlert, { type: 'error', variant: 'tonal', class: 'mb-3' }, () => error.value),
        message.value && h(VAlert, { type: 'success', variant: 'tonal', class: 'mb-3', closable: true, 'onClick:close': () => message.value = '' }, () => message.value),
        loading.value && h('div', { class: 'wy-loading' }, [h(VProgressCircular, { indeterminate: true, color: 'primary' }), h('span', '正在读取微云状态...')]),
        h('div', { class: 'wy-summary' }, [
          h('div', { class: 'wy-summary-main' }, [
            h('div', { class: 'wy-summary-title' }, '扫码登录与 Cookie 状态'),
            h('div', { class: 'wy-summary-sub' }, status.value.last_status || '尚未运行'),
          ]),
          h('div', { class: 'wy-summary-actions' }, [
            h(VChip, { color: stateColor.value, variant: 'tonal', size: 'small' }, () => stateText.value),
            h(VChip, { color: status.value.enabled ? 'success' : 'default', variant: 'tonal', size: 'small' }, () => status.value.enabled ? '已启用' : '未启用'),
          ]),
        ]),
        h('div', { class: 'wy-status-strip' }, [
          stat('登录方式', status.value.login_type_title, 'mdi-login-variant'),
          stat('浏览器', status.value.browser_mode_title, 'mdi-web'),
          stat('Cookie 数量', String(status.value.cookie_count ?? 0), 'mdi-counter', status.value.has_cookie ? 'success' : 'grey'),
          stat('检测周期', status.value.check_cron, 'mdi-clock-outline'),
        ]),
        h(VRow, { dense: true, class: 'mt-2' }, () => [
          h(VCol, { cols: 12, md: 4 }, () => h(VCard, { variant: 'outlined', class: 'wy-card-panel' }, () => [
            h(VCardText, null, [
              h('div', { class: 'wy-section-line' }, [
                h('span', '二维码'),
                h(VBtn, { size: 'small', variant: 'tonal', prependIcon: 'mdi-delete-outline', color: 'error', loading: busy.value, onClick: () => action('clear_cookie', '已清除 Cookie') }, () => '清除'),
              ]),
              h('div', { class: 'wy-qr-panel' }, [
                qrcodeSrc.value
                  ? h('img', { src: qrcodeSrc.value, class: 'wy-qr-img', alt: '微云登录二维码' })
                  : h('div', { class: 'wy-qr-empty' }, [h(VIcon, { icon: 'mdi-qrcode-scan', size: '44' }), h('span', '启动扫码后显示二维码')]),
              ]),
              h('div', { class: 'wy-action-row wy-action-row--stack' }, [
                h(VBtn, { color: 'primary', prependIcon: 'mdi-play-circle-outline', loading: busy.value, block: true, onClick: () => action('start_login', '已启动微云扫码登录') }, () => '启动扫码'),
                h(VBtn, { variant: 'tonal', prependIcon: 'mdi-shield-check-outline', loading: busy.value, block: true, onClick: () => action('check_cookie', '检测完成') }, () => '检测 Cookie'),
                h(VBtn, { variant: 'tonal', prependIcon: 'mdi-cloud-sync-outline', loading: busy.value, block: true, onClick: () => action('sync_openlist', '同步完成') }, () => '同步 OpenList'),
              ]),
            ]),
          ])),
          h(VCol, { cols: 12, md: 8 }, () => h(VCard, { variant: 'outlined', class: 'wy-card-panel' }, () => [
            h(VCardText, null, [
              h('div', { class: 'wy-section-line' }, [
                h('span', 'Cookie 管理'),
                h(VBtn, { size: 'small', variant: 'tonal', prependIcon: 'mdi-content-copy', disabled: !status.value.cookie, onClick: copyCookie }, () => '复制'),
              ]),
              h('div', { class: 'wy-cookie-private' }, [
                h(VIcon, { icon: status.value.has_cookie ? 'mdi-shield-lock-outline' : 'mdi-cookie-alert-outline', size: '42', color: status.value.has_cookie ? 'success' : 'grey' }),
                h('div', { class: 'wy-cookie-private-title' }, status.value.has_cookie ? 'Cookie 已安全保存' : '暂无 Cookie'),
                h('div', { class: 'wy-cookie-private-desc' }, status.value.has_cookie ? `已保存 ${status.value.cookie_count ?? 0} 个 Cookie，主页默认隐藏明文。` : '启动扫码登录后会自动保存 Cookie。'),
              ]),
              h('div', { class: 'wy-cookie-meta' }, [
                meta('最近状态', status.value.last_status),
                meta('最近检测', status.value.last_check_status || status.value.last_check),
                meta('OpenList 同步', status.value.last_openlist_sync_status || status.value.last_openlist_sync),
              ]),
            ]),
          ])),
        ]),
        h(VCard, { variant: 'outlined', class: 'wy-card-panel wy-timeline-panel mt-3' }, () => [
          h(VCardText, null, [
            h('div', { class: 'wy-section-line' }, [h('span', '近期结果')]),
            h(VDivider, { class: 'my-3' }),
            timeline('最近登录', status.value.last_run, 'mdi-history'),
            timeline('检测结果', status.value.last_check_status, 'mdi-shield-check-outline', status.value.last_check_status ? 'success' : 'grey'),
            timeline('最近检测', status.value.last_check, 'mdi-clock-check-outline'),
            timeline('OpenList 同步', status.value.last_openlist_sync_status, 'mdi-cloud-sync-outline', status.value.last_openlist_sync_status ? 'info' : 'grey'),
            timeline('同步时间', status.value.last_openlist_sync, 'mdi-calendar-clock'),
          ]),
        ]),
      ]),
    ]);
  },
});
