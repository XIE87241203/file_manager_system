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
     * @description 用途说明：异步获取当前日志目录的总大小与文件数量
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {size_bytes, file_count}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getLogDirectorySize(onSuccess, onError) {
        Request.get('/api/system/logs/size', {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：提交更新后的全站系统配置
     * @param {Object} data - 入参说明：包含 duplicate_check, file_name_entry, user_data, log_management 的完整配置对象
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
     * @description 用途说明：获取当前登录用户信息（登录名与是否管理员）
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {username, is_admin}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getCurrentUser(onSuccess, onError) {
        Request.get('/api/user/me')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：获取用户列表（仅管理员）
     * @param {Function} onSuccess - 入参说明：成功回调，参数为用户数组 [{id, username, is_admin, create_time}]
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getUserList(onSuccess, onError) {
        Request.get('/api/user/list')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：新增用户（仅系统管理员），密码以 SHA-256 哈希传输，系统使用者可同时提交仓库权限
     * @param {string} username - 入参说明：登录名
     * @param {string} passwordHash - 入参说明：密码的 SHA-256 哈希
     * @param {boolean} isAdmin - 入参说明：True 为系统管理员，False 为系统使用者
     * @param {Array} permissions - 入参说明：仓库权限列表 [{repo_id, permission}]
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    addUser(username, passwordHash, isAdmin, permissions, onSuccess, onError) {
        Request.post('/api/user/add', {
            username: username,
            password_hash: passwordHash,
            is_admin: isAdmin,
            permissions: permissions
        })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：获取指定用户的完整仓库权限配置（仅系统管理员）
     * @param {number} id - 入参说明：目标用户 ID
     * @param {Function} onSuccess - 入参说明：成功回调，参数为仓库权限列表
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getUserPermissions(id, onSuccess, onError) {
        Request.get(`/api/user/permissions?id=${encodeURIComponent(id)}`, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：整体更新指定系统使用者的仓库权限（仅系统管理员）
     * @param {number} id - 入参说明：目标用户 ID
     * @param {Array} permissions - 入参说明：仓库权限列表 [{repo_id, permission}]
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    updateUserPermissions(id, permissions, onSuccess, onError) {
        Request.post('/api/user/update_permissions', { id: id, permissions: permissions })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：删除用户（仅管理员）
     * @param {number} id - 入参说明：待删除用户 ID
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    deleteUser(id, onSuccess, onError) {
        Request.post('/api/user/delete', { id: id })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：修改指定用户密码（仅管理员），新密码以 SHA-256 哈希传输
     * @param {number} id - 入参说明：目标用户 ID
     * @param {string} passwordHash - 入参说明：新密码的 SHA-256 哈希
     * @param {Function} onSuccess - 入参说明：成功回调
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    updateUserPassword(id, passwordHash, onSuccess, onError) {
        Request.post('/api/user/update_password', { id: id, password_hash: passwordHash })
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：分页获取指定用户的登录历史（仅管理员）
     * @param {number} id - 入参说明：目标用户 ID
     * @param {number} page - 入参说明：页码（从 1 开始）
     * @param {number} pageSize - 入参说明：每页条数
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {total, page, page_size, list:[{login_time, ip}]}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getLoginHistory(id, page, pageSize, onSuccess, onError) {
        const query = new URLSearchParams({ id: id, page: page, page_size: pageSize }).toString();
        Request.get('/api/user/login_history?' + query, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};
