/**
 * @description 首页相关 API 请求封装
 */
const HomeRequest = {
    /**
     * @description 用途说明：获取当前登录用户的系统角色与仓库权限
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {username, is_admin, repo_permission}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息
     * @returns {void} - 返回值说明：无
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
     * @description 用途说明：从后端获取文件仓库详情统计信息
     * @param {Function} onSuccess - 入参说明：成功回调，参数为统计数据对象
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息
     * @returns {void} - 返回值说明：无
     */
    getRepoDetail(onSuccess, onError) {
        Request.get('/api/file_repository/detail')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：手动触发后端重新计算文件仓库统计数据
     * @param {Function} onSuccess - 入参说明：成功回调，参数为更新后的统计数据对象
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息
     * @returns {void} - 返回值说明：无
     */
    calculateRepoDetail(onSuccess, onError) {
        // 首页有自定义的加载动画，故关闭全局 Loading 蒙版
        Request.post('/api/file_repository/detail/calculate', {}, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：从后端获取应用版本号
     * @param {Function} onSuccess - 入参说明：成功回调，参数为版本数据对象
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息
     * @returns {void} - 返回值说明：无
     */
    getAppVersion(onSuccess, onError) {
        Request.get('/api/system/version', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：同步首页选择的语言到后端全局配置，使接口提示与页面文案保持一致
     * @param {string} language - 入参说明：语言标识 zh 或 en
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息
     * @returns {void} - 返回值说明：无
     */
    updateLanguage(language, onSuccess, onError) {
        Request.post('/api/setting/update', { user_data: { language } }, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：执行注销登录，通知后端清理会话
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调
     * @returns {void} - 返回值说明：无
     */
    logout(onSuccess, onError) {
        Request.post('/api/logout', {})
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};
