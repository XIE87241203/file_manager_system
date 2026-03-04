/**
 * 用途说明：封装运行日志相关的 API 请求。
 */
const LogsRequest = {
    /**
     * 用途说明：获取系统运行日志。
     * 入参说明：
     *   params (object) - 包含 lines, level, exclude_api, keyword 等筛选参数。
     *   onSuccess (function) - 成功回调，接收返回的 data。
     *   onError (function) - 失败回调，接收错误消息字符串。
     * 返回值说明：无
     */
    fetchLogs(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get(`/api/system/logs?${query}`, {}, false)
            .then(res => {
                if (res.status === 'success') {
                    onSuccess(res.data);
                } else {
                    onError(res.message);
                }
            })
            .catch(err => {
                const errorMsg = err.message || (typeof I18nManager !== 'undefined' ? I18nManager.t('common.network_error') : 'Network error');
                onError(errorMsg);
            });
    }
};
