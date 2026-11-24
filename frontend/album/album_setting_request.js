/**
 * 用途说明：相册设置页面 API 请求封装，负责读取与更新缩略图存储路径配置。
 * 每个方法均提供成功回调 (onSuccess) 与错误回调 (onError)。
 */
const AlbumSettingRequest = {
    /**
     * 用途说明：获取相册设置。
     * 入参说明：
     *   onSuccess (Function) - 成功回调，参数为 {thumbnail_dir, thumbnail_dir_effective}。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/album/settings', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：更新相册缩略图存储路径。
     * 入参说明：
     *   thumbnailDir (string) - 新的缩略图存储路径。
     *   onSuccess (Function) - 成功回调，参数为更新后的设置对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    updateSettings(thumbnailDir, onSuccess, onError) {
        Request.post('/api/album/settings', { thumbnail_dir: thumbnailDir }, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：启动缩略图物理同步任务。
     * 入参说明：
     *   onSuccess (Function) - 成功回调。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    startThumbnailSync(onSuccess, onError) {
        Request.post('/api/file_repository/thumbnail/sync/start')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：停止缩略图物理同步任务。
     * 入参说明：
     *   onSuccess (Function) - 成功回调。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    stopThumbnailSync(onSuccess, onError) {
        Request.post('/api/file_repository/thumbnail/sync/stop')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取缩略图物理同步任务进度。
     * 入参说明：
     *   onSuccess (Function) - 成功回调，参数为进度数据对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    getThumbnailSyncProgress(onSuccess, onError) {
        Request.get('/api/file_repository/thumbnail/sync/progress', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};