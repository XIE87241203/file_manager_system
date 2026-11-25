/**
 * 用途说明：相册设置页面 API 请求封装，负责缩略图设置、当前用户权限与人脸识别任务。
 * 每个方法均提供成功回调 (onSuccess) 与错误回调 (onError)。
 */
const AlbumSettingRequest = {
    /**
     * 用途说明：获取相册设置。
     * 入参说明：
     *   onSuccess (Function) - 成功回调，参数为 {thumbnail_dir, thumbnail_dir_effective, thumbnail_size, auto_face_recognition}。
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
     * 用途说明：更新相册缩略图设置与自动人脸识别开关。
     * 入参说明：
     *   thumbnailDir (string) - 新的缩略图存储路径。
     *   thumbnailSize (number) - 缩略图最大边长（像素），较长边不超过此尺寸。
     *   autoFaceRecognition (boolean) - 新建索引发现新增图片时是否自动加入人脸识别队列。
     *   onSuccess (Function) - 成功回调，参数为更新后的设置对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    updateSettings(thumbnailDir, thumbnailSize, autoFaceRecognition, onSuccess, onError) {
        const payload = {
            thumbnail_dir: thumbnailDir,
            thumbnail_size: thumbnailSize
        };
        if (typeof autoFaceRecognition === 'boolean') {
            payload.auto_face_recognition = autoFaceRecognition;
        }
        Request.post('/api/album/settings', payload, {}, false)
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
    },

    /**
     * 用途说明：获取当前用户在所选仓库中的权限。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getCurrentUser(onSuccess, onError) {
        Request.get('/api/user/me', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：获取人脸识别状态、剩余数量和已保存人脸数量。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getFaceStatus(onSuccess, onError) {
        Request.get('/api/album/face/status', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：将当前仓库未识别图片去重加入队列，并启动或恢复单线程人脸识别任务。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    startFaceRecognition(onSuccess, onError) {
        Request.post('/api/album/face/start', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：暂停当前人脸识别任务，保留队列与已处理数据。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    pauseFaceRecognition(onSuccess, onError) {
        Request.post('/api/album/face/pause', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：停止当前人脸识别任务，并清空该仓库整个待识别队列，保留已处理数据。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    stopFaceRecognition(onSuccess, onError) {
        Request.post('/api/album/face/stop', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：停止识别任务并清除当前仓库的人脸数据。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    clearFaceRecognitionData(onSuccess, onError) {
        Request.post('/api/album/face/clear', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};