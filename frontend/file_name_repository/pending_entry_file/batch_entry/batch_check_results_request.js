/**
 * 用途说明：批量检测结果页面的 API 请求封装。
 */

const BatchCheckResultsRequest = {
    /**
     * 用途说明：获取当前批量检测任务的状态。
     * 入参说明：
     *   - onSuccess (Function): 成功回调，入参为后端返回的数据对象 (包含 status 和 progress)
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    getStatus: function(onSuccess, onError) {
        Request.get('/api/file_name_repository/pending_entry/check_status', {}, false)
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || I18nManager.t('batch_check.get_status_failed'));
                }
            })
            .catch(err => {
                if (onError) onError(I18nManager.t('batch_check.network_error'));
            });
    },

    /**
     * 用途说明：获取检测结果列表。
     * 入参说明：
     *   - params (Object): 包含 sort_by (string) 和 order_asc (boolean) 的排序参数
     *   - onSuccess (Function): 成功回调，入参为后端返回的结果数据数组
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    getResults: function(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_name_repository/pending_entry/check_results?' + query)
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || I18nManager.t('batch_check.get_results_failed'));
                }
            })
            .catch(err => {
                if (onError) onError(I18nManager.t('batch_check.network_error'));
            });
    },

    /**
     * 用途说明：清理后端任务状态及缓存。
     * 入参说明：
     *   - onSuccess (Function): 成功回调，入参为后端返回的数据对象
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    clearTask: function(onSuccess, onError) {
        Request.post('/api/file_name_repository/pending_entry/check_clear')
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || I18nManager.t('batch_check.clear_task_failed'));
                }
            })
            .catch(err => {
                if (onError) onError(I18nManager.t('batch_check.network_error'));
            });
    },

    /**
     * 用途说明：确认录入选中的文件名。
     * 入参说明：
     *   - fileNames (Array<string>): 待录入的文件名数组
     *   - onSuccess (Function): 成功回调，入参为后端返回的数据对象 (包含 count)
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    confirmImport: function(fileNames, onSuccess, onError) {
        Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames })
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || I18nManager.t('batch_check.import_failed'));
                }
            })
            .catch(err => {
                if (onError) onError(I18nManager.t('batch_check.network_error'));
            });
    }
};
