import { importShared } from './__federation_fn_import-054b33c3.js';

const config = '';

const Config_vue_vue_type_style_index_0_scoped_c80f89c3_lang = '';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {reactive,ref,computed,watch} = await importShared('vue');

// 配置分组定义：只描述数据，渲染交给模板，避免手改编译产物。
const CONFIG_GROUPS = [
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
];

/**
 * 把 cron 表达式翻成一句人话，避免顶栏直接甩出六段式原文。
 */
function humanizeCron(expr) {
  const raw = String(expr || '').trim();
  if (!raw) return '未启用'
  if (raw === '0 */6 * * *') return '每 6 小时'
  const hourly = raw.match(/^0 \*\/(\d+) \* \* \*$/);
  if (hourly) return `每 ${hourly[1]} 小时`
  const everyMinutes = raw.match(/^\*\/(\d+) \* \* \* \*$/);
  if (everyMinutes) return `每 ${everyMinutes[1]} 分钟`
  const daily = raw.match(/^(\d+) (\d+) \* \* \*$/);
  if (daily) return `每天 ${String(daily[2]).padStart(2, '0')}:${String(daily[1]).padStart(2, '0')}`
  return raw
}

const _sfc_main = {
  name: 'Config',
  props: {
    initialConfig: { type: Object, default: () => ({}) },
    api: { type: [Object, Function], default: null },
  },
  emits: ['save', 'close', 'switch'],
  setup(props, { emit }) {
    const form = reactive({});
    const openSections = reactive({ primary: true });
    const saving = ref(false);
    const savedHint = ref('');
    let savedTimer = null;

    watch(
      () => props.initialConfig,
      (value) => {
        Object.keys(form).forEach((key) => delete form[key]);
        Object.assign(form, value || {});
      },
      { immediate: true, deep: true },
    );

    const wideModels = new Set(['login_url', 'qrcode_public_base_url', 'openlist_url', 'openlist_token', 'check_cron']);

    const collapsedGroups = computed(() => CONFIG_GROUPS.filter((group) => group.key !== 'primary'));

    const checkCycleText = computed(() => humanizeCron(form.check_cron));

    // Cookie 卡片同时体现"有没有"和"数量"，失效时不再只显示一个 0。
    const cookieState = computed(() => {
      const count = Number(form.last_cookie_count ?? 0);
      const status = String(form.last_status || '');
      if (!count) return { text: '未获取', color: 'warning' }
      if (status.indexOf('失败') >= 0) return { text: `可能失效（${count} 项）`, color: 'warning' }
      return { text: `${count} 项`, color: 'success' }
    });

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
    ]);

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
      form[def[1]] = def[0] === 'number' ? Number(value || 0) : value;
    }

    function onToggle(group, event) {
      openSections[group.key] = event.target.open;
    }

    function save() {
      emit('save', { ...form });
      // 保存后给出明确回馈：原来点完几乎没有任何反应，用户不知道成没成。
      saving.value = true;
      savedHint.value = '正在保存…';
      if (savedTimer) clearTimeout(savedTimer);
      savedTimer = setTimeout(() => {
        saving.value = false;
        savedHint.value = '已提交保存，配置将在插件重载后生效。';
      }, 700);
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
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "wy-config" };
const _hoisted_2 = { class: "wy-console-hero" };
const _hoisted_3 = { class: "wy-hint" };
const _hoisted_4 = { class: "wy-hero-actions" };
const _hoisted_5 = { class: "wy-console-stats" };
const _hoisted_6 = { class: "wy-console-label" };
const _hoisted_7 = { class: "wy-console-value" };
const _hoisted_8 = { class: "wy-quick-bar" };
const _hoisted_9 = { class: "wy-quick-main" };
const _hoisted_10 = { class: "wy-quick-switch" };
const _hoisted_11 = { class: "wy-quick-switch" };
const _hoisted_12 = { class: "wy-quick-actions" };
const _hoisted_13 = { class: "wy-quick-hint" };
const _hoisted_14 = { class: "wy-settings-sheet" };
const _hoisted_15 = ["open", "onToggle"];
const _hoisted_16 = { class: "wy-section-head" };
const _hoisted_17 = { class: "wy-section-copy" };
const _hoisted_18 = { class: "wy-section-title" };
const _hoisted_19 = { class: "wy-section-desc" };
const _hoisted_20 = { class: "wy-section-body" };
const _hoisted_21 = {
  key: 1,
  class: "wy-archive-grid"
};
const _hoisted_22 = { class: "wy-archive-body" };
const _hoisted_23 = { class: "wy-archive-label" };
const _hoisted_24 = { class: "wy-archive-value" };
const _hoisted_25 = {
  key: 0,
  class: "wy-switch-grid"
};
const _hoisted_26 = { class: "wy-switch-copy" };
const _hoisted_27 = { class: "wy-switch-title" };
const _hoisted_28 = {
  key: 0,
  class: "wy-switch-hint"
};

function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, {
      class: "wy-console-card",
      elevation: 0
    }, {
      default: _withCtx(() => [
        _createElementVNode("div", _hoisted_2, [
          _createElementVNode("div", null, [
            _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-h6" }, "微云 Cookie 助手 · 设置", -1)),
            _createElementVNode("div", _hoisted_3, " 扫码登录分成两步：先在上方打开「启用插件」，再勾选「保存后立即运行一次」并保存。最近状态：" + _toDisplayString($setup.form.last_status || '未运行'), 1)
          ]),
          _createElementVNode("div", _hoisted_4, [
            _createVNode(_component_VChip, {
              color: $setup.form.enabled ? 'success' : 'default',
              variant: "tonal",
              size: "small"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString($setup.form.enabled ? '已启用' : '未启用'), 1)
              ]),
              _: 1
            }, 8, ["color"]),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              "prepend-icon": "mdi-close",
              onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode("关闭", -1)
              ]))]),
              _: 1
            })
          ])
        ]),
        _createElementVNode("div", _hoisted_5, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.stats, (item) => {
            return (_openBlock(), _createElementBlock("div", {
              key: item.label,
              class: "wy-console-stat"
            }, [
              _createElementVNode("div", _hoisted_6, [
                _createVNode(_component_VIcon, {
                  icon: item.icon,
                  size: "15",
                  color: item.color,
                  class: "mr-1"
                }, null, 8, ["icon", "color"]),
                _createTextVNode(_toDisplayString(item.label), 1)
              ]),
              _createElementVNode("div", _hoisted_7, _toDisplayString(item.value || '—'), 1)
            ]))
          }), 128))
        ]),
        _createElementVNode("div", _hoisted_8, [
          _createElementVNode("div", _hoisted_9, [
            _createElementVNode("div", _hoisted_10, [
              _cache[5] || (_cache[5] = _createElementVNode("div", { class: "wy-quick-copy" }, [
                _createElementVNode("div", { class: "wy-switch-title" }, "启用插件"),
                _createElementVNode("div", { class: "wy-switch-hint" }, "关闭后命令与周期检测停止。")
              ], -1)),
              _createVNode(_component_VSwitch, {
                modelValue: $setup.form.enabled,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => (($setup.form.enabled) = $event)),
                color: "primary",
                density: "comfortable",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _createElementVNode("div", _hoisted_11, [
              _cache[6] || (_cache[6] = _createElementVNode("div", { class: "wy-quick-copy" }, [
                _createElementVNode("div", { class: "wy-switch-title" }, "保存后立即运行一次"),
                _createElementVNode("div", { class: "wy-switch-hint" }, "保存后跑一次扫码登录，结束后自动关闭。")
              ], -1)),
              _createVNode(_component_VSwitch, {
                modelValue: $setup.form.onlyonce,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => (($setup.form.onlyonce) = $event)),
                color: "primary",
                density: "comfortable",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ])
          ]),
          _createElementVNode("div", _hoisted_12, [
            _createVNode(_component_VBtn, {
              color: "primary",
              "prepend-icon": "mdi-content-save-outline",
              loading: $setup.saving,
              onClick: $setup.save
            }, {
              default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                _createTextVNode("保存设置", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "onClick"]),
            _createElementVNode("div", _hoisted_13, _toDisplayString($setup.savedHint), 1)
          ])
        ]),
        _createElementVNode("div", _hoisted_14, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.collapsedGroups, (group) => {
            return (_openBlock(), _createElementBlock("details", {
              key: group.key,
              class: _normalizeClass(["wy-section", `wy-section--${group.key}`]),
              open: !!$setup.openSections[group.key],
              onToggle: $event => ($setup.onToggle(group, $event))
            }, [
              _createElementVNode("summary", _hoisted_16, [
                _createElementVNode("div", _hoisted_17, [
                  _createElementVNode("div", _hoisted_18, [
                    _createVNode(_component_VIcon, {
                      icon: group.icon,
                      size: "18"
                    }, null, 8, ["icon"]),
                    _createElementVNode("span", null, _toDisplayString(group.title), 1)
                  ]),
                  _createElementVNode("div", _hoisted_19, _toDisplayString(group.desc), 1)
                ]),
                _createVNode(_component_VIcon, {
                  class: "wy-section-chevron",
                  icon: "mdi-chevron-down",
                  size: "20"
                })
              ]),
              _createElementVNode("div", _hoisted_20, [
                (group.alert)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "warning",
                      variant: "tonal",
                      density: "compact",
                      class: "mb-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(group.alert), 1)
                      ]),
                      _: 2
                    }, 1024))
                  : _createCommentVNode("", true),
                (group.compact)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_21, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.fields, (def) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: def[0],
                          class: "wy-archive-item"
                        }, [
                          _createVNode(_component_VIcon, {
                            icon: def[2],
                            color: def[3] || 'primary',
                            size: "18"
                          }, null, 8, ["icon", "color"]),
                          _createElementVNode("div", _hoisted_22, [
                            _createElementVNode("div", _hoisted_23, _toDisplayString(def[1]), 1),
                            _createElementVNode("div", _hoisted_24, _toDisplayString($setup.archiveValue(def[0])), 1)
                          ])
                        ]))
                      }), 128))
                    ]))
                  : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                      ($setup.switchFields(group).length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_25, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.switchFields(group), (def) => {
                              return (_openBlock(), _createElementBlock("div", {
                                key: def[1],
                                class: "wy-switch-tile"
                              }, [
                                _createElementVNode("div", _hoisted_26, [
                                  _createElementVNode("div", _hoisted_27, _toDisplayString(def[2]), 1),
                                  (def[3])
                                    ? (_openBlock(), _createElementBlock("div", _hoisted_28, _toDisplayString(def[3]), 1))
                                    : _createCommentVNode("", true)
                                ]),
                                _createVNode(_component_VSwitch, {
                                  modelValue: $setup.form[def[1]],
                                  "onUpdate:modelValue": $event => (($setup.form[def[1]]) = $event),
                                  color: "primary",
                                  density: "compact",
                                  "hide-details": "",
                                  inset: ""
                                }, null, 8, ["modelValue", "onUpdate:modelValue"])
                              ]))
                            }), 128))
                          ]))
                        : _createCommentVNode("", true),
                      ($setup.inputFields(group).length)
                        ? (_openBlock(), _createBlock(_component_VRow, {
                            key: 1,
                            dense: "",
                            class: "wy-field-grid"
                          }, {
                            default: _withCtx(() => [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList($setup.inputFields(group), (def) => {
                                return (_openBlock(), _createBlock(_component_VCol, {
                                  key: def[1],
                                  cols: "12",
                                  md: $setup.wideModels.has(def[1]) ? 12 : 6
                                }, {
                                  default: _withCtx(() => [
                                    (def[0] === 'select')
                                      ? (_openBlock(), _createBlock(_component_VSelect, {
                                          key: 0,
                                          modelValue: $setup.form[def[1]],
                                          "onUpdate:modelValue": $event => (($setup.form[def[1]]) = $event),
                                          label: def[2],
                                          items: def[4],
                                          variant: "outlined",
                                          density: "comfortable",
                                          hint: def[3],
                                          "persistent-hint": ""
                                        }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "items", "hint"]))
                                      : (_openBlock(), _createBlock(_component_VTextField, {
                                          key: 1,
                                          modelValue: $setup.form[def[1]],
                                          "onUpdate:modelValue": [$event => (($setup.form[def[1]]) = $event), (v) => $setup.onInput(def, v)],
                                          label: def[2],
                                          variant: "outlined",
                                          density: "comfortable",
                                          hint: def[3],
                                          "persistent-hint": "",
                                          type: def[0] === 'password' ? 'password' : 'text',
                                          clearable: def[0] === 'text' || def[0] === 'password'
                                        }, null, 8, ["modelValue", "onUpdate:modelValue", "label", "hint", "type", "clearable"]))
                                  ]),
                                  _: 2
                                }, 1032, ["md"]))
                              }), 128))
                            ]),
                            _: 2
                          }, 1024))
                        : _createCommentVNode("", true)
                    ], 64))
              ])
            ], 42, _hoisted_15))
          }), 128))
        ])
      ]),
      _: 1
    })
  ]))
}
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['render',_sfc_render],['__scopeId',"data-v-c80f89c3"]]);

export { CONFIG_GROUPS, _export_sfc as _, Config as default, humanizeCron };
