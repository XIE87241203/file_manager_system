/**
 * @description 系统设置页面 API 请求封装
 */
const SettingRequest = {
    /**
     * @description 用途说明：从后端获取系统配置总览数据
     * @param {Function} onSuccess - 入参说明：成功回调，参数为配置数据对象
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/setting/get')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：提交更新后的全站系统配置
     * @param {Object} data - 入参说明：包含 file_repository, duplicate_check, file_name_entry, user_data 的完整配置对象
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    updateSettings(data, onSuccess, onError) {
        Request.post('/api/setting/update', data)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：清空曾录入文件名库记录
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    clearAlreadyEntered(onSuccess, onError) {
        Request.post('/api/file_name_repository/already_entered/clear')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：清空待录入文件名库记录
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    clearPendingEntry(onSuccess, onError) {
        Request.post('/api/file_name_repository/pending_entry/clear')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：清空所有有效文件索引记录
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    clearHistory(onSuccess, onError) {
        Request.post('/api/file_repository/clear_history')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：清空视频特征库
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    clearVideoFeatures(onSuccess, onError) {
        Request.post('/api/file_repository/clear_video_features')
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：启动缩略图物理同步任务
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
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
     * @description 用途说明：停止缩略图物理同步任务
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
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
     * @description 用途说明：获取缩略图物理同步任务进度
     * @param {Function} onSuccess - 入参说明：成功回调，参数为进度数据对象
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
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
