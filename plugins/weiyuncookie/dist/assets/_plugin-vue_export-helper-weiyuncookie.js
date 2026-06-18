function unwrapResponse(response) {
  const data = response?.data ?? response;
  if (data && typeof data === 'object' && 'data' in data) return data.data;
  return data;
}
async function postPluginApi(api, path, payload = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪');
  const response = await api.post(`plugin/weiyuncookie/${path}`, payload);
  return unwrapResponse(response);
}
async function getPluginApi(api, path) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪');
  const response = await api.get(`plugin/weiyuncookie/${path}`);
  return unwrapResponse(response);
}
export { getPluginApi as g, postPluginApi as p };
