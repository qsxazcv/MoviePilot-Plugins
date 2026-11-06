import { importShared } from './__federation_fn_import-054b33c3.js';
import { _ as _export_sfc, humanizeCron } from './__federation_expose_Config-f09a8639.js';

/**
 * MoviePilot V3 插件 API 调用封装。
 *
 * 宿主插件 API 可能返回 { success, message, data } 三段式 envelope，
 * 这里统一解包到业务数据，页面组件只关心结果本身。
 */
function unwrapResponse(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(`plugin/weiyuncookie/${path}`, payload);
  return unwrapResponse(response)
}

async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(`plugin/weiyuncookie/${path}`);
  return unwrapResponse(response)
}

const page = '';

const Page_vue_vue_type_style_index_0_scoped_05b0d5ea_lang = '';

const {ref,computed,onMounted,onBeforeUnmount} = await importShared('vue');

const _sfc_main = {
  name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(props) {
    const loading = ref(false);
    const busy = ref(false);
    const error = ref('');
    const message = ref('');
    const status = ref({});
    let timer = null;
    let messageTimer = null;

    const qrcodeSrc = computed(() => (status.value?.has_qrcode && status.value?.qrcode ? status.value.qrcode : ''));
    const stateColor = computed(() => (status.value.running ? 'warning' : status.value.has_cookie ? 'success' : 'default'));
    const stateText = computed(() => (status.value.running ? '扫码进行中' : status.value.has_cookie ? 'Cookie 已保存' : '等待登录'));

    // 状态卡只放"当前值"，历史时间统一收到运行记录里，避免同一信息出现两次。
    const statusStats = computed(() => [
      { label: '登录方式', value: status.value.login_type_title, icon: 'mdi-login-variant', color: 'primary' },
      { label: '浏览器', value: status.value.browser_mode_title, icon: 'mdi-web', color: 'primary' },
      { label: 'Cookie 数量', value: `${status.value.cookie_count ?? 0} 个`, icon: 'mdi-counter', color: status.value.has_cookie ? 'success' : 'grey' },
      { label: '检测周期', value: humanizeCron(status.value.check_cron), icon: 'mdi-clock-outline', color: 'primary' },
    ]);

    // 运行记录：合并原先「近期结果」与「Cookie 管理」的重复项，只保留一份。
    const timeline = computed(() => [
      { label: '最近登录', value: status.value.last_run, icon: 'mdi-history', color: 'primary' },
      { label: '最近检测', value: status.value.last_check, icon: 'mdi-clock-check-outline', color: 'primary' },
      { label: '检测结果', value: status.value.last_check_status, icon: 'mdi-shield-check-outline', color: status.value.last_check_status ? 'success' : 'grey' },
      { label: '最近同步', value: status.value.last_openlist_sync, icon: 'mdi-calendar-clock', color: 'primary' },
      { label: '同步结果', value: status.value.last_openlist_sync_status, icon: 'mdi-cloud-sync-outline', color: status.value.last_openlist_sync_status ? 'info' : 'grey' },
    ]);

    // 底部把空白换成一句有用的话，而不是留一大片空。
    const tipText = computed(() => {
      if (status.value.running) return '二维码有效期较短，请尽快用微信或 QQ 扫码。'
      if (!status.value.has_cookie) return '扫码成功后会自动保存 Cookie，并按配置同步到 OpenList。'
      if (status.value.enabled) return '插件已启用，会按检测周期自动检查 Cookie 是否失效。'
      return '插件当前未启用，仅手动操作可用；到「设置」里可以开启。'
    });

    // 未生成二维码时的三步引导，把左侧空白变成有用的说明
    const steps = [
      { icon: 'mdi-numeric-1-circle-outline', title: '启动扫码', desc: '点击上方按钮，自动打开微云登录页并生成二维码。' },
      { icon: 'mdi-numeric-2-circle-outline', title: '扫码登录', desc: '用微信或 QQ 扫描二维码，二维码有时效，请尽快完成。' },
      { icon: 'mdi-numeric-3-circle-outline', title: '自动保存', desc: '登录成功后自动保存 Cookie，并按配置同步到 OpenList。' },
    ];

    function clearMessage() {
      if (messageTimer) {
        clearTimeout(messageTimer);
        messageTimer = null;
      }
      message.value = '';
    }

    function showMessage(text, delay = 4000) {
      clearMessage();
      message.value = text;
      messageTimer = setTimeout(() => {
        message.value = '';
        messageTimer = null;
      }, delay);
    }

    async function load(silent = false) {
      if (!silent) loading.value = true;
      error.value = '';
      try {
        status.value = (await getPluginApi(props.api, 'status')) || {};
      } catch (err) {
        error.value = '加载状态失败：' + (err?.message || err);
      } finally {
        loading.value = false;
      }
    }

    async function action(path, ok) {
      busy.value = true;
      error.value = '';
      clearMessage();
      try {
        const result = await postPluginApi(props.api, path);
        showMessage(result?.message || ok || '操作已提交');
        await load(true);
      } catch (err) {
        error.value = (ok || '操作') + '失败：' + (err?.message || err);
      } finally {
        busy.value = false;
      }
    }

    function eventCopy(text) {
      if (typeof document === 'undefined' || !document.addEventListener) return false
      let wrote = false;
      const listener = (event) => {
        event.preventDefault();
        if (event.clipboardData) {
          event.clipboardData.setData('text/plain', text);
          wrote = true;
        }
      };
      document.addEventListener('copy', listener);
      let ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (err) {
        ok = false;
      } finally {
        document.removeEventListener('copy', listener);
      }
      return ok && wrote
    }

    async function copyCookie() {
      let text = '';
      error.value = '';
      clearMessage();
      try {
        const latest = (await getPluginApi(props.api, 'cookie')) || {};
        status.value = {
          ...status.value,
          has_cookie: latest.has_cookie ?? status.value.has_cookie,
          cookie_length: latest.cookie_length ?? status.value.cookie_length,
        };
        const grant = await postPluginApi(props.api, 'request_cookie_reveal');
        const token = grant?.token;
        if (!token) throw new Error(grant?.message || '未取得一次性授权')
        const revealed = await postPluginApi(props.api, 'reveal_cookie', { reveal_token: token });
        text = revealed?.cookie || '';
      } catch (err) {
        error.value = '读取 Cookie 失败：' + (err?.message || err);
        return
      }
      if (!text) {
        error.value = '当前没有可复制的 Cookie，请先扫码登录';
        return
      }
      const copiedByEvent = eventCopy(text);
      if (copiedByEvent) {
        showMessage(`Cookie 已复制到剪贴板（${text.length} 字符）`);
        return
      }
      try {
        if (navigator?.clipboard?.writeText && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          showMessage(`Cookie 已复制到剪贴板（${text.length} 字符）`);
          return
        }
      } catch (err) {
        /* 回退失败则走统一错误提示 */
      }
      error.value = '复制失败，请刷新页面后重试';
    }

    onMounted(() => {
      load();
      timer = setInterval(() => load(true), 3000);
    });

    onBeforeUnmount(() => {
      if (timer) clearInterval(timer);
      clearMessage();
    });

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
};

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "wy-page" };
const _hoisted_2 = { class: "wy-page-wrap" };
const _hoisted_3 = {
  key: 2,
  class: "wy-loading"
};
const _hoisted_4 = { class: "wy-summary" };
const _hoisted_5 = { class: "wy-summary-main" };
const _hoisted_6 = { class: "wy-summary-sub" };
const _hoisted_7 = { class: "wy-summary-actions" };
const _hoisted_8 = { class: "wy-status-strip" };
const _hoisted_9 = { class: "wy-status-label" };
const _hoisted_10 = ["title"];
const _hoisted_11 = { class: "wy-section-line" };
const _hoisted_12 = {
  key: 0,
  class: "wy-qr-panel"
};
const _hoisted_13 = ["src"];
const _hoisted_14 = ["disabled"];
const _hoisted_15 = {
  key: 2,
  class: "wy-steps"
};
const _hoisted_16 = { class: "wy-step-title" };
const _hoisted_17 = { class: "wy-step-desc" };
const _hoisted_18 = { class: "wy-action-row wy-action-row--stack" };
const _hoisted_19 = { class: "wy-action-pair" };
const _hoisted_20 = { class: "wy-cookie-state-body" };
const _hoisted_21 = { class: "wy-cookie-state-title" };
const _hoisted_22 = { class: "wy-cookie-state-desc" };
const _hoisted_23 = { class: "wy-timeline-grid" };
const _hoisted_24 = { class: "wy-timeline-body" };
const _hoisted_25 = { class: "wy-timeline-label" };
const _hoisted_26 = ["title"];
const _hoisted_27 = { class: "wy-tip" };

function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  const _component_VToolbarTitle = _resolveComponent("VToolbarTitle");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VToolbar, {
      class: "wy-toolbar",
      density: "comfortable"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VToolbarTitle, null, {
          default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
            _createTextVNode("微云 Cookie 助手", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-play-circle-outline",
          variant: "text",
          title: "启动扫码登录",
          loading: $setup.busy,
          onClick: _cache[0] || (_cache[0] = $event => ($setup.action('start_login', '已启动微云扫码登录')))
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-shield-check-outline",
          variant: "text",
          title: "立即检测",
          loading: $setup.busy,
          onClick: _cache[1] || (_cache[1] = $event => ($setup.action('check_cookie', '检测完成')))
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-cloud-sync-outline",
          variant: "text",
          title: "同步 OpenList",
          loading: $setup.busy,
          onClick: _cache[2] || (_cache[2] = $event => ($setup.action('sync_openlist', '同步完成')))
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-refresh",
          variant: "text",
          title: "刷新",
          loading: $setup.loading,
          onClick: _cache[3] || (_cache[3] = $event => ($setup.load()))
        }, null, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          icon: "mdi-cog-outline",
          variant: "text",
          title: "设置",
          onClick: _cache[4] || (_cache[4] = $event => (_ctx.$emit('switch')))
        }),
        _createVNode(_component_VBtn, {
          icon: "mdi-close",
          variant: "text",
          title: "关闭",
          onClick: _cache[5] || (_cache[5] = $event => (_ctx.$emit('close')))
        })
      ]),
      _: 1
    }),
    _createElementVNode("div", _hoisted_2, [
      ($setup.error)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 0,
            type: "error",
            variant: "tonal",
            class: "mb-3"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString($setup.error), 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      ($setup.message)
        ? (_openBlock(), _createBlock(_component_VAlert, {
            key: 1,
            type: "success",
            variant: "tonal",
            class: "mb-3",
            closable: "",
            "onClick:close": $setup.clearMessage
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString($setup.message), 1)
            ]),
            _: 1
          }, 8, ["onClick:close"]))
        : _createCommentVNode("", true),
      ($setup.loading)
        ? (_openBlock(), _createElementBlock("div", _hoisted_3, [
            _createVNode(_component_VProgressCircular, {
              indeterminate: "",
              color: "primary"
            }),
            _cache[13] || (_cache[13] = _createElementVNode("span", null, "正在读取微云状态...", -1))
          ]))
        : _createCommentVNode("", true),
      _createElementVNode("div", _hoisted_4, [
        _createElementVNode("div", _hoisted_5, [
          _cache[14] || (_cache[14] = _createElementVNode("div", { class: "wy-summary-title" }, "扫码登录与 Cookie 状态", -1)),
          _createElementVNode("div", _hoisted_6, _toDisplayString($setup.status.last_status || '尚未运行'), 1)
        ]),
        _createElementVNode("div", _hoisted_7, [
          _createVNode(_component_VChip, {
            color: $setup.stateColor,
            variant: "tonal",
            size: "small"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString($setup.stateText), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createVNode(_component_VChip, {
            color: $setup.status.enabled ? 'success' : 'default',
            variant: "tonal",
            size: "small"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString($setup.status.enabled ? '已启用' : '未启用'), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createVNode(_component_VBtn, {
            size: "small",
            color: "primary",
            "prepend-icon": "mdi-play-circle-outline",
            loading: $setup.busy,
            onClick: _cache[6] || (_cache[6] = $event => ($setup.action('start_login', '已启动微云扫码登录')))
          }, {
            default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
              _createTextVNode(" 启动扫码 ", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "tonal",
            "prepend-icon": "mdi-content-copy",
            disabled: !$setup.status.has_cookie,
            onClick: $setup.copyCookie
          }, {
            default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
              _createTextVNode(" 复制 Cookie ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled", "onClick"])
        ])
      ]),
      _createElementVNode("div", _hoisted_8, [
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.statusStats, (item) => {
          return (_openBlock(), _createElementBlock("div", {
            key: item.label,
            class: "wy-status-item"
          }, [
            _createElementVNode("div", _hoisted_9, [
              _createVNode(_component_VIcon, {
                icon: item.icon,
                size: "15",
                color: item.color,
                class: "mr-1"
              }, null, 8, ["icon", "color"]),
              _createTextVNode(_toDisplayString(item.label), 1)
            ]),
            _createElementVNode("div", {
              class: "wy-status-value",
              title: item.value
            }, _toDisplayString(item.value || '—'), 9, _hoisted_10)
          ]))
        }), 128))
      ]),
      _createVNode(_component_VRow, {
        dense: "",
        class: "wy-main-grid mt-2"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCol, {
            cols: "12",
            md: "5",
            class: "wy-col-flex"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCard, {
                variant: "outlined",
                class: "wy-card-panel wy-card-fill"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardText, { class: "wy-card-body" }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_11, [
                        _cache[18] || (_cache[18] = _createElementVNode("span", null, "二维码", -1)),
                        _createVNode(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          "prepend-icon": "mdi-delete-outline",
                          color: "error",
                          loading: $setup.busy,
                          onClick: _cache[7] || (_cache[7] = $event => ($setup.action('clear_cookie', '已清除 Cookie')))
                        }, {
                          default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                            _createTextVNode(" 清除 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading"])
                      ]),
                      ($setup.qrcodeSrc)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                            _createElementVNode("img", {
                              src: $setup.qrcodeSrc,
                              class: "wy-qr-img",
                              alt: "微云登录二维码"
                            }, null, 8, _hoisted_13)
                          ]))
                        : (_openBlock(), _createElementBlock("button", {
                            key: 1,
                            type: "button",
                            class: "wy-qr-idle",
                            disabled: $setup.busy,
                            onClick: _cache[8] || (_cache[8] = $event => ($setup.action('start_login', '已启动微云扫码登录')))
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-qrcode-scan",
                              size: "26"
                            }),
                            _cache[19] || (_cache[19] = _createElementVNode("span", null, "点击生成登录二维码", -1))
                          ], 8, _hoisted_14)),
                      (!$setup.qrcodeSrc)
                        ? (_openBlock(), _createElementBlock("ol", _hoisted_15, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.steps, (step) => {
                              return (_openBlock(), _createElementBlock("li", {
                                key: step.title
                              }, [
                                _createVNode(_component_VIcon, {
                                  icon: step.icon,
                                  size: "16"
                                }, null, 8, ["icon"]),
                                _createElementVNode("div", null, [
                                  _createElementVNode("div", _hoisted_16, _toDisplayString(step.title), 1),
                                  _createElementVNode("div", _hoisted_17, _toDisplayString(step.desc), 1)
                                ])
                              ]))
                            }), 128))
                          ]))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_18, [
                        _createVNode(_component_VBtn, {
                          color: "primary",
                          "prepend-icon": "mdi-play-circle-outline",
                          loading: $setup.busy,
                          block: "",
                          onClick: _cache[9] || (_cache[9] = $event => ($setup.action('start_login', '已启动微云扫码登录')))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString($setup.qrcodeSrc ? '重新生成二维码' : '启动扫码'), 1)
                          ]),
                          _: 1
                        }, 8, ["loading"]),
                        _createElementVNode("div", _hoisted_19, [
                          _createVNode(_component_VBtn, {
                            variant: "text",
                            size: "small",
                            "prepend-icon": "mdi-shield-check-outline",
                            loading: $setup.busy,
                            onClick: _cache[10] || (_cache[10] = $event => ($setup.action('check_cookie', '检测完成')))
                          }, {
                            default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                              _createTextVNode(" 检测 Cookie ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["loading"]),
                          _createVNode(_component_VBtn, {
                            variant: "text",
                            size: "small",
                            "prepend-icon": "mdi-cloud-sync-outline",
                            loading: $setup.busy,
                            onClick: _cache[11] || (_cache[11] = $event => ($setup.action('sync_openlist', '同步完成')))
                          }, {
                            default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                              _createTextVNode(" 同步 OpenList ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["loading"])
                        ])
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_VCol, {
            cols: "12",
            md: "7",
            class: "wy-col-flex"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCard, {
                variant: "outlined",
                class: "wy-card-panel wy-card-fill"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardText, { class: "wy-card-body" }, {
                    default: _withCtx(() => [
                      _cache[22] || (_cache[22] = _createElementVNode("div", { class: "wy-section-line" }, [
                        _createElementVNode("span", null, "运行记录")
                      ], -1)),
                      _createElementVNode("div", {
                        class: _normalizeClass(["wy-cookie-state", { 'is-empty': !$setup.status.has_cookie }])
                      }, [
                        _createVNode(_component_VIcon, {
                          icon: $setup.status.has_cookie ? 'mdi-shield-lock-outline' : 'mdi-cookie-alert-outline',
                          size: "24",
                          color: $setup.status.has_cookie ? 'success' : 'grey'
                        }, null, 8, ["icon", "color"]),
                        _createElementVNode("div", _hoisted_20, [
                          _createElementVNode("div", _hoisted_21, _toDisplayString($setup.status.has_cookie ? 'Cookie 已安全保存' : '暂无 Cookie'), 1),
                          _createElementVNode("div", _hoisted_22, _toDisplayString($setup.status.has_cookie
                      ? `已保存 ${$setup.status.cookie_count ?? 0} 个 Cookie，明文默认隐藏。`
                      : '启动扫码登录后会自动保存 Cookie。'), 1)
                        ])
                      ], 2),
                      _createElementVNode("div", _hoisted_23, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.timeline, (item) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: item.label,
                            class: "wy-timeline-row"
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: item.icon,
                              color: item.color,
                              size: "16"
                            }, null, 8, ["icon", "color"]),
                            _createElementVNode("div", _hoisted_24, [
                              _createElementVNode("div", _hoisted_25, _toDisplayString(item.label), 1),
                              _createElementVNode("div", {
                                class: "wy-timeline-value",
                                title: item.value
                              }, _toDisplayString(item.value || '—'), 9, _hoisted_26)
                            ])
                          ]))
                        }), 128))
                      ]),
                      _createElementVNode("div", _hoisted_27, [
                        _createVNode(_component_VIcon, {
                          icon: "mdi-lightbulb-on-outline",
                          size: "15"
                        }),
                        _createElementVNode("span", null, _toDisplayString($setup.tipText), 1)
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ])
  ]))
}
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['render',_sfc_render],['__scopeId',"data-v-05b0d5ea"]]);

export { Page as default };
