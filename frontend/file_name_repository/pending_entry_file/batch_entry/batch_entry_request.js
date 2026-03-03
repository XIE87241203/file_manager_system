/**
 * 用途说明：批量录入文件名页面的 API 请求封装。
 */

const BatchEntryRequest = {
    /**
     * 用途说明：调用后端接口启动批量检测任务。
     * 入参说明：
     *   - fileNames (Array<string>): 需要检测的文件名数组
     *   - onSuccess (Function): 成功回调，入参为后端返回的数据对象
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    startCheck: function(fileNames, onSuccess, onError) {
        Request.post('/api/file_name_repository/pending_entry/check_batch', { file_names: fileNames }, {}, false)
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || '启动检测失败');
                }
            })
            .catch(err => {
                if (onError) onError('网络请求异常');
            });
    },

    /**
     * 用途说明：调用后端接口获取当前检测任务的进度和状态。
     * 入参说明：
     *   - onSuccess (Function): 成功回调，入参为包含 status 和 progress 的对象
     *   - onError (Function): 错误回调，入参为错误信息字符串
     * 返回值说明：无
     */
    getStatus: function(onSuccess, onError) {
        Request.get('/api/file_name_repository/pending_entry/check_status', {}, false)
            .then(res => {
                if (res.status === 'success') {
                    if (onSuccess) onSuccess(res.data);
                } else {
                    if (onError) onError(res.message || '获取状态失败');
                }
            })
            .catch(err => {
                if (onError) onError('网络请求异常');
            });
    }
};
