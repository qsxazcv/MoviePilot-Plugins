# 前端开发说明

本插件的前端是 MoviePilot V3 的 Vue 联邦组件，源码与构建产物都在本目录。

## 目录结构

```
weiyuncookie/
├── src/
│   ├── components/
│   │   ├── Config.vue      # 设置页
│   │   └── Page.vue        # 详情页
│   ├── styles/
│   │   ├── config.css      # 设置页样式
│   │   └── page.css        # 详情页样式
│   ├── api.js              # 宿主插件 API 调用封装
│   └── dev/
│       └── preview.js      # 本地预览入口（仅开发用，不进产物）
├── dist/assets/            # 构建产物，宿主实际加载这里
├── index.html              # 本地预览页
├── vite.config.js          # 构建与模块联邦配置
└── package.json
```

## 构建

```bash
cd plugins.v3/weiyuncookie
npm install
npm run build
```

产物输出到 `dist/assets/`，暴露 `./Config` 与 `./Page` 两个联邦模块。

### 不要提交

`node_modules/` 已被 `.gitignore` 排除。`dist/` 需要提交——宿主直接加载它，不走构建。

## 本地预览

```bash
npm run dev
```

打开提示的地址即可看到设置页（使用内置 demo 数据）。

## 样式约束

联邦组件的 CSS 会注入宿主页面，**必须避免污染**：

- `vite.config.js` 中的 `vuetifyFilter` 会清空 `vuetify` 与 `@mdi` 的样式树
- 移除其余来源中带 `.v-` / `.mdi-` 的全局规则
- 插件自身的类名统一使用 `wy-` 前缀

构建后可以这样自检：

```bash
grep -c '\.v-' dist/assets/style-*.css   # 应为 0
```

## 改动流程

1. 改 `src/` 下的源码
2. `npm install && npm run build`
3. 提交源码与 `dist/` 一起
4. 提升 `__init__.py` 的 `plugin_version` 与 `package.v3.json` 的版本

> 历史提示：1.2.6 及更早版本的 `dist` 是手工修改的编译产物，没有源码可追溯。
> 自 1.2.7 起改为源码构建，请勿再直接编辑 `dist/`。
