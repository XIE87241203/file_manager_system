/**
 * 用途说明：回收站页面的 API 请求封装，通过回调函数处理成功和失败的情况。
 */
const RecycleBinAPI = {
    /**
     * 用途说明：分页获取回收站文件列表
     * 入参说明：params (Object) - 查询参数；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    getList(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_repository/recycle_bin/list?' + query)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || '网络请求失败'));
    },

    /**
     * 用途说明：从回收站恢复文件
     * 入参说明：filePaths (Array) - 文件路径数组；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    restoreFiles(filePaths, onSuccess, onError) {
        Request.post('/api/file_repository/restore_from_recycle_bin', { file_paths: filePaths })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || '网络请求失败'));
    },

    /**
     * 用途说明：批量彻底删除回收站中的文件
     * 入参说明：filePaths (Array) - 文件路径数组；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    deleteFiles(filePaths, onSuccess, onError) {
        // 彻底删除进度条开启时，禁用默认 mask
        Request.post('/api/file_repository/clear_recycle_bin', { file_paths: filePaths }, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || '网络请求失败'));
    },

    /**
     * 用途说明：清空整个回收站
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    clearAll(onSuccess, onError) {
        // 清空进度条开启时，禁用默认 mask
        Request.post('/api/file_repository/clear_recycle_bin', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || '网络请求失败'));
    },

    /**
     * 用途说明：获取清理回收站任务的执行进度
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    getDeleteProgress(onSuccess, onError) {
        // 轮询进度时一律不显示 mask，防止页面抖动
        Request.get('/api/file_repository/clear_recycle_bin/progress', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || '网络请求失败'));
    }
};
