/**
 * @description 登录页面 API 请求封装
 */
const LoginRequest = {
    /**
     * @description 用途说明：从后端获取应用版本号
     * @param {Function} onSuccess - 入参说明：成功回调，入参为后端返回的数据对象
     * @param {Function} onError - 入参说明：失败回调，入参为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getVersion(onSuccess, onError) {
        Request.get('/api/system/version', {}, false)
            .then(res => {
                if (res.status === 'success') {
                    onSuccess(res.data);
                } else {
                    onError(res.message);
                }
            })
            .catch(err => {
                onError(err.message || I18nManager.t('common.network_error'));
            });
    },

    /**
     * @description 用途说明：提交登录凭证进行身份验证
     * @param {Object} data - 入参说明：包含 username 和 password_hash 的登录对象
     * @param {Function} onSuccess - 入参说明：成功回调，入参为包含 token 的响应对象
     * @param {Function} onError - 入参说明：失败回调，入参为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    login(data, onSuccess, onError) {
        Request.post('/api/login', data)
            .then(res => {
                if (res.status === 'success') {
                    onSuccess(res.data);
                } else {
                    onError(res.message);
                }
            })
            .catch(err => {
                onError(err.message || I18nManager.t('common.network_error'));
            });
    }
};
