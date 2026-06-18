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
    const VTextarea = C('VTextarea');
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
        error.value = '复制失败，请手动复制文本框内容';
      }
    }

    function card(label, value, icon, color = 'primary') {
      return h('div', { class: 'wy-status-card' }, [
        h('div', { class: 'wy-status-label' }, [h(VIcon, { icon, size: '15', class: 'mr-1', color }), label]),
        h('div', { class: 'wy-status-value' }, value || '—'),
      ]);
    }

    function featureCard(title, main, sub, icon, color = 'primary') {
      return h('div', { class: 'wy-feature-card' }, [
        h('div', { class: 'wy-feature-head' }, [
          h('div', [h(VIcon, { icon, color, size: '18', class: 'mr-1' }), h('span', title)]),
          h(VChip, { size: 'x-small', variant: 'tonal', color }, () => main),
        ]),
        h('div', { class: 'wy-feature-main' }, sub),
        h('div', { class: 'wy-feature-sub' }, title === '扫码登录' ? '二维码会随登录成功或超时自动隐藏' : '状态来自插件实时接口'),
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
        h('div', { class: 'wy-status-grid' }, [
          card('插件状态', status.value.enabled ? '已启用' : '未启用', 'mdi-power', status.value.enabled ? 'success' : 'grey'),
          card('运行状态', status.value.running ? '扫码进行中' : '空闲', 'mdi-progress-clock', status.value.running ? 'warning' : 'primary'),
          card('登录方式', status.value.login_type_title, 'mdi-login-variant'),
          card('浏览器模式', status.value.browser_mode_title, 'mdi-web'),
          card('Cookie 状态', status.value.has_cookie ? '已保存' : '未保存', 'mdi-cookie-outline', status.value.has_cookie ? 'success' : 'error'),
          card('Cookie 数量', String(status.value.cookie_count ?? 0), 'mdi-counter'),
          card('最近登录', status.value.last_run, 'mdi-history'),
          card('检测周期', status.value.check_cron, 'mdi-clock-outline'),
        ]),
        h('div', { class: 'wy-feature-grid' }, [
          featureCard('扫码登录', status.value.running ? '进行中' : '待启动', status.value.last_status || '尚未运行', 'mdi-qrcode-scan', status.value.running ? 'warning' : 'primary'),
          featureCard('Cookie 检测', status.value.last_check_status || '未检测', status.value.last_check || '暂无检测时间', 'mdi-shield-check-outline', status.value.last_check_status ? 'success' : 'default'),
          featureCard('OpenList 同步', status.value.last_openlist_sync_status || '未同步', status.value.last_openlist_sync || '暂无同步时间', 'mdi-cloud-sync-outline', status.value.last_openlist_sync_status ? 'info' : 'default'),
        ]),
        h('div', { class: 'wy-data-hint' }, [h(VIcon, { icon: 'mdi-refresh', size: '16' }), '页面每 3 秒刷新一次状态；扫码、检测、同步逻辑保持原插件行为。']),
        h(VRow, { dense: true, class: 'mt-2' }, () => [
          h(VCol, { cols: 12, md: 5 }, () => h(VCard, { variant: 'outlined', class: 'wy-card-panel' }, () => [
            h(VCardText, null, [
              h('div', { class: 'wy-section-line' }, [
                h('span', '二维码与操作'),
                h(VBtn, { size: 'small', variant: 'tonal', prependIcon: 'mdi-delete-outline', color: 'error', loading: busy.value, onClick: () => action('clear_cookie', '已清除 Cookie') }, () => '清除 Cookie'),
              ]),
              h('div', { class: 'wy-qr-panel' }, [
                qrcodeSrc.value
                  ? h('img', { src: qrcodeSrc.value, class: 'wy-qr-img', alt: '微云登录二维码' })
                  : h('div', { class: 'wy-qr-empty' }, [h(VIcon, { icon: 'mdi-qrcode-scan', size: '46' }), h('span', '启动扫码后这里会显示二维码')]),
              ]),
              h('div', { class: 'wy-hint' }, status.value.has_qrcode ? '请使用当前登录方式扫码，成功后 Cookie 会自动保存。' : '当前没有二维码，可点击启动扫码生成。'),
              h(VDivider, { class: 'my-3' }),
              h('div', { class: 'wy-action-row' }, [
                h(VBtn, { color: 'primary', prependIcon: 'mdi-play-circle-outline', loading: busy.value, onClick: () => action('start_login', '已启动微云扫码登录') }, () => '启动扫码'),
                h(VBtn, { variant: 'tonal', prependIcon: 'mdi-shield-check-outline', loading: busy.value, onClick: () => action('check_cookie', '检测完成') }, () => '检测 Cookie'),
                h(VBtn, { variant: 'tonal', prependIcon: 'mdi-cloud-sync-outline', loading: busy.value, onClick: () => action('sync_openlist', '同步完成') }, () => '同步 OpenList'),
              ]),
            ]),
          ])),
          h(VCol, { cols: 12, md: 7 }, () => h(VCard, { variant: 'outlined', class: 'wy-card-panel' }, () => [
            h(VCardText, null, [
              h('div', { class: 'wy-section-line' }, [
                h('span', '完整 Cookie'),
                h(VBtn, { size: 'small', variant: 'tonal', prependIcon: 'mdi-content-copy', disabled: !status.value.cookie, onClick: copyCookie }, () => '复制'),
              ]),
              status.value.cookie
                ? h(VTextarea, { modelValue: status.value.cookie, readonly: true, rows: 11, 'auto-grow': false, variant: 'outlined', class: 'mt-3 wy-cookie-textarea' })
                : h('div', { class: 'wy-empty' }, [h(VIcon, { icon: 'mdi-cookie-alert-outline', size: '38' }), h('div', '暂无 Cookie，请先扫码登录。')]),
            ]),
          ])),
        ]),
      ]),
    ]);
  },
});
