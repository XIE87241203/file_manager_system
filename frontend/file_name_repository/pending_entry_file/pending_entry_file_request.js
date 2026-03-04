/**
 * 用途说明：待录入文件名库相关 API 请求封装
 */
const PendingEntryAPI = {
    /**
     * 用途说明：获取待录入文件名列表
     * 入参说明：params: Object - 查询参数 (page, limit, sort_by, order_asc, search); onSuccess: Function - 成功回调; onError: Function - 失败回调
     * 返回值说明：无
     */
    getList(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_name_repository/pending_entry/list?' + query)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：批量删除待录入记录
     * 入参说明：ids: Array - 记录 ID 列表; onSuccess: Function - 成功回调; onError: Function - 失败回调
     * 返回值说明：无
     */
    batchDeletePending(ids, onSuccess, onError) {
        Request.post('/api/file_name_repository/pending_entry/batch_delete', { ids: ids })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：批量添加曾录入记录
     * 入参说明：fileNames: Array - 文件名列表; onSuccess: Function - 成功回调; onError: Function - 失败回调
     * 返回值说明：无
     */
    addToAlreadyEntered(fileNames, onSuccess, onError) {
        Request.post('/api/file_name_repository/already_entered/add', { file_names: fileNames })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取系统配置
     * 入参说明：onSuccess: Function - 成功回调; onError: Function - 失败回调
     * 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/setting/get')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};
