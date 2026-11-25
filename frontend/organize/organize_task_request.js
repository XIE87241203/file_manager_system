/**
 * @description 文件整理页面 API 请求封装（整理设置读取、任务启动、待整理分页、保存）
 */
const OrganizeTaskRequest = {
    /**
     * @description 用途说明：获取当前仓库的整理设置，用于判断是否已配置待整理/已整理目录
     * @param {Function} onSuccess - 入参说明：成功回调，参数为设置数据 {pending_dirs, organized_dir, extensions, rename_script_path}
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
     * @description 用途说明：启动整理任务（后端扫描待整理目录并按后缀筛选建立队列）
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {total, remaining, organized_dir}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    startTask(onSuccess, onError) {
        Request.post('/api/organize/task/start', {})
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：分页获取剩余待整理文件列表（含类型、大小与建议文件名）
     * @param {number} page - 入参说明：页码（从 1 开始）
     * @param {number} pageSize - 入参说明：每页条数
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {total, remaining, page, page_size, items}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getPending(page, pageSize, onSuccess, onError) {
        Request.get(`/api/organize/task/pending?page=${page}&page_size=${pageSize}`)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：保存当前文件整理结果（按新文件名移动到已整理目录并写入整理历史，后端自动保留原文件后缀）
     * @param {string} path - 入参说明：待整理文件完整路径
     * @param {string} newName - 入参说明：整理后文件名（不含后缀，后端保存时自动拼接原后缀）
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {remaining, total, organized_path, organized_name}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    saveFile(path, newName, onSuccess, onError) {
        Request.post('/api/organize/task/save', { path: path, new_name: newName })
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：跳过当前待整理文件（仅从本次任务队列移除，不动文件；重新扫描后会再次出现）
     * @param {string} path - 入参说明：待跳过文件完整路径
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {remaining, total}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    skipFile(path, onSuccess, onError) {
        Request.post('/api/organize/task/skip', { path: path })
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：将当前待整理文件移入回收站（只打标记不删物理文件，可在回收站恢复）
     * @param {string} path - 入参说明：待移入回收站的文件完整路径
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {remaining, total}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    recycleFile(path, onSuccess, onError) {
        Request.post('/api/organize/task/recycle', { path: path })
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：构造待整理文件的预览地址（图片/视频流式接口，携带 Token 供标签直接加载）
     * @param {string} path - 入参说明：待整理文件完整路径（须在当前任务队列中）
     * @returns {string} - 返回值说明：带 path 与 token 查询参数的预览 URL
     */
    buildPreviewUrl(path) {
        const token = Request.getCookie('token');
        return `/api/organize/task/preview?path=${encodeURIComponent(path)}&token=${encodeURIComponent(token || '')}`;
    }
};