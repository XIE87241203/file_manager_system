/**
 * @description 文件查重页面 API 请求封装
 */
const DuplicateCheckAPI = {
    /**
     * @description 用途说明：向后端发送请求开始查重任务
     * @param {string} mode - 入参说明：查重模式 ('global' 全局查重 / 'incremental' 新增查重)
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    startCheck(mode, onSuccess, onError) {
        Request.post('/api/file_repository/duplicate/check', { mode: mode }, {}, true)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：向后端发送请求停止查重任务
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    stopCheck(onSuccess, onError) {
        Request.post('/api/file_repository/duplicate/stop', {}, {}, true)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：获取当前查重任务的进度
     * @param {Function} onSuccess - 入参说明：成功回调，参数为进度数据对象
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    getProgress(onSuccess, onError) {
        Request.get('/api/file_repository/duplicate/progress', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：分页获取查重结果数据
     * @param {Object} params - 入参说明：查询参数 (page, limit, similarity_type, file_type)
     * @param {Function} onSuccess - 入参说明：成功回调，参数为分页数据列表
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    getDuplicateList(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_repository/duplicate/list?' + query, {}, true)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：获取最近一次查重的完成时间
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {time, duration} 对象
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    getLatestCheckTime(onSuccess, onError) {
        Request.get('/api/file_repository/duplicate/latest_check_time', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：调用通用移入回收站 API 批量处理文件
     * @param {Array} paths - 入参说明：待删除文件路径数组
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    moveToRecycleBin(paths, onSuccess, onError) {
        Request.post('/api/file_repository/move_to_recycle_bin', { file_paths: paths }, {}, true)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    },

    /**
     * @description 用途说明：按需生成或复用单个文件缩略图（与相册缩略图共用同一接口）
     * @param {string} filePath - 入参说明：文件完整路径
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {file_path, thumbnail_path}
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    ensureThumbnail(filePath, onSuccess, onError) {
        Request.post('/api/file_repository/thumbnail/ensure', { file_path: filePath }, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：获取系统设置
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/setting/get')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.error')));
    }
};
