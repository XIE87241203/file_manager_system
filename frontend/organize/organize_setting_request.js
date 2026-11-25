/**
 * @description 整理设置页面 API 请求封装
 */
const OrganizeSettingRequest = {
    /**
     * @description 用途说明：从后端获取当前仓库的整理设置
     * @param {Function} onSuccess - 入参说明：成功回调，参数为设置数据对象 {pending_dirs, organized_dir, extensions, rename_script_path, size_op, size_value, size_unit}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/organize/setting/get')
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：提交更新后的整理设置
     * @param {Object} data - 入参说明：设置对象 {pending_dirs: string[], organized_dir: string, extensions: string[], rename_script_path: string, size_op: string, size_value: number, size_unit: string}
     * @param {Function} onSuccess - 入参说明：成功回调，参数为后端返回的归一化设置数据
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    updateSettings(data, onSuccess, onError) {
        Request.post('/api/organize/setting/update', data)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};