/**
 * 用途说明：多仓库管理相关 API 请求封装，供首页与设置页等共享调用。
 * 每个方法均提供成功回调 (onSuccess) 与错误回调 (onError)。
 */
const RepositoryRequest = {
    /**
     * 用途说明：获取仓库列表。
     * 入参说明：
     *   onSuccess (Function) - 成功回调，参数为仓库数组 [{id, name, create_time}]。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    list(onSuccess, onError) {
        Request.get('/api/repository/list', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data || []);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：创建新仓库。
     * 入参说明：
     *   name (string) - 仓库名称。
     *   onSuccess (Function) - 成功回调，参数为新仓库信息 {id, name, create_time}。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    create(name, onSuccess, onError) {
        Request.post('/api/repository/create', { name })
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：删除指定仓库（保留磁盘物理文件）。
     * 入参说明：
     *   id (number) - 仓库 ID。
     *   onSuccess (Function) - 成功回调。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    delete(id, onSuccess, onError) {
        Request.post('/api/repository/delete', { id })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取指定仓库的独立配置。
     * 入参说明：
     *   id (number) - 仓库 ID。
     *   onSuccess (Function) - 成功回调，参数为仓库配置对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    getConfig(id, onSuccess, onError) {
        Request.get(`/api/repository/config?id=${id}`, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：更新指定仓库的独立配置。
     * 入参说明：
     *   id (number) - 仓库 ID。
     *   config (Object) - 待更新的配置字段对象。
     *   onSuccess (Function) - 成功回调。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    updateConfig(id, config, onSuccess, onError) {
        Request.post('/api/repository/config/update', { id, ...config })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};