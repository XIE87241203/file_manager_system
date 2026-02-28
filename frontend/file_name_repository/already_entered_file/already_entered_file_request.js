/**
 * 用途说明：曾录入文件名库 API 请求封装
 */

const AlreadyEnteredAPI = {
    /**
     * 用途说明：获取曾录入文件名列表
     * 入参说明：params: { page, limit, sort_by, order_asc, search }
     * onSuccess: 成功回调
     * onError: 失败回调
     * 返回值说明：无直接返回值，通过回调函数返回数据
     */
    getList(params, onSuccess, onError) {
        const query = new URLSearchParams(params).toString();
        Request.get('/api/file_name_repository/already_entered/list?' + query)
            .then(res => {
                if (res.status === 'success') {
                    onSuccess && onSuccess(res.data);
                } else {
                    onError && onError(res.message);
                }
            })
            .catch(err => onError && onError(err));
    },

    /**
     * 用途说明：新增曾录入文件名
     * 入参说明：fileNames: 文件名数组
     * onSuccess: 成功回调
     * onError: 失败回调
     * 返回值说明：无直接返回值，通过回调函数返回数据
     */
    add(fileNames, onSuccess, onError) {
        Request.post('/api/file_name_repository/already_entered/add', { file_names: fileNames })
            .then(res => {
                if (res.status === 'success') {
                    onSuccess && onSuccess(res);
                } else {
                    onError && onError(res.message);
                }
            })
            .catch(err => onError && onError(err));
    },

    /**
     * 用途说明：批量删除曾录入文件名
     * 入参说明：ids: ID 数组
     * onSuccess: 成功回调
     * onError: 失败回调
     * 返回值说明：无直接返回值，通过回调函数返回数据
     */
    batchDelete(ids, onSuccess, onError) {
        Request.post('/api/file_name_repository/already_entered/batch_delete', { ids: ids })
            .then(res => {
                if (res.status === 'success') {
                    onSuccess && onSuccess(res);
                } else {
                    onError && onError(res.message);
                }
            })
            .catch(err => onError && onError(err));
    },

    /**
     * 用途说明：清空曾录入文件名
     * onSuccess: 成功回调
     * onError: 失败回调
     * 返回值说明：无直接返回值，通过回调函数返回数据
     */
    clear(onSuccess, onError) {
        Request.post('/api/file_name_repository/already_entered/clear', {})
            .then(res => {
                if (res.status === 'success') {
                    onSuccess && onSuccess(res);
                } else {
                    onError && onError(res.message);
                }
            })
            .catch(err => onError && onError(err));
    },

    /**
     * 用途说明：获取系统配置
     * onSuccess: 成功回调
     * onError: 失败回调
     * 返回值说明：无直接返回值，通过回调函数返回配置数据
     */
    getSettings(onSuccess, onError) {
        Request.get('/api/setting/get')
            .then(res => {
                if (res.status === 'success') {
                    onSuccess && onSuccess(res.data);
                } else {
                    onError && onError(res.message);
                }
            })
            .catch(err => onError && onError(err));
    }
};
