/**
 * 用途说明：文件仓库页面的 API 请求封装，通过回调函数处理成功和失败的情况。
 */
const FileRepositoryAPI = {
    /**
     * 用途说明：获取文件列表
     * 入参说明：params (Object) - 查询参数；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    getFileList(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_repository/list?' + query)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：将选中的文件移入回收站
     * 入参说明：filePaths (Array) - 文件路径数组；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    moveToRecycleBin(filePaths, onSuccess, onError) {
        Request.post('/api/file_repository/move_to_recycle_bin', { file_paths: filePaths })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：启动文件扫描/索引任务
     * 入参说明：fullScan (Boolean) - 是否全量扫描；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    startScan(fullScan, onSuccess, onError) {
        Request.post('/api/file_repository/scan', { full_scan: fullScan })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：停止正在进行的扫描任务
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    stopScan(onSuccess, onError) {
        Request.post('/api/file_repository/stop', {})
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取扫描任务进度
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    getProgress(onSuccess, onError) {
        Request.get('/api/file_repository/progress', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：启动缩略图生成任务
     * 入参说明：rebuildAll (Boolean) - 是否重新生成所有缩略图；onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    startThumbnailGeneration(rebuildAll, onSuccess, onError) {
        Request.post('/api/file_repository/thumbnail/start', { rebuild_all: rebuildAll })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：停止正在进行的缩略图生成任务
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    stopThumbnailGeneration(onSuccess, onError) {
        Request.post('/api/file_repository/thumbnail/stop', {})
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取缩略图生成队列中的剩余数量
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
     * 返回值说明：无
     */
    getThumbnailQueueCount(onSuccess, onError) {
        Request.get('/api/file_repository/thumbnail/queue_count', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取系统全局设置
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调
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
