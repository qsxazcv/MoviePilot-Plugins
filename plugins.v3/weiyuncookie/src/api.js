/**
 * MoviePilot V3 插件 API 调用封装。
 *
 * 宿主插件 API 可能返回 { success, message, data } 三段式 envelope，
 * 这里统一解包到业务数据，页面组件只关心结果本身。
 */
function unwrapResponse(response) {
  const data = response?.data ?? response
  if (data && typeof data === 'object' && 'data' in data) return data.data
  return data
}

export async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(`plugin/weiyuncookie/${path}`, payload)
  return unwrapResponse(response)
}

export async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(`plugin/weiyuncookie/${path}`)
  return unwrapResponse(response)
}
