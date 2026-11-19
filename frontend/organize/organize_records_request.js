/**
 * @description 整理记录页面 API 请求封装（分页查询、CSV 导出下载）
 */
const OrganizeRecordsRequest = {
    /**
     * @description 用途说明：分页获取当前仓库的整理记录（后端按整理时间倒序返回，时间已转为本地时间）
     * @param {number} page - 入参说明：页码（从 1 开始）
     * @param {number} pageSize - 入参说明：每页条数
     * @param {Function} onSuccess - 入参说明：成功回调，参数为 {total, page, page_size, items}
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    getRecords(page, pageSize, onSuccess, onError) {
        Request.get(`/api/organize/records/list?page=${page}&page_size=${pageSize}`)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError((err && err.message) || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：导出全部整理记录为 CSV 并触发浏览器下载。
     *   后端仓库上下文仅识别 X-Repo-Id 请求头，故使用 fetch 携带鉴权头获取文件流，
     *   再通过 Blob + 临时链接触发下载（文件名优先取响应头 Content-Disposition）。
     * @param {Function} onSuccess - 入参说明：成功回调，参数为实际下载的文件名
     * @param {Function} onError - 入参说明：失败回调，参数为错误信息字符串
     * @returns {void} - 返回值说明：无
     */
    exportRecords(onSuccess, onError) {
        const headers = {};
        const token = Request.getCookie('token');
        if (token) headers['Authorization'] = token;
        if (typeof RepoContext !== 'undefined') headers['X-Repo-Id'] = String(RepoContext.get());

        fetch(`${Request.baseUrl}/api/organize/records/export`, { headers })
            .then(async response => {
                if (response.status === 401) {
                    // 与 Request 工具类一致：登录失效时清理 Token 并跳转登录页
                    Request.eraseCookie('token');
                    Toast.show(I18nManager.t('common.login_expired'));
                    setTimeout(() => { window.location.href = '/login/login.html'; }, 1500);
                    throw new Error('Login expired');
                }
                const contentType = response.headers.get('content-type') || '';
                if (!response.ok || contentType.includes('application/json')) {
                    // 非文件流响应：解析统一 JSON 错误信息
                    let message = I18nManager.t('organize.records.export_failed');
                    try {
                        const result = await response.json();
                        if (result && result.message) message = result.message;
                    } catch (e) { /* 响应体非 JSON 时沿用默认错误文案 */ }
                    throw new Error(message);
                }
                const blob = await response.blob();
                const filename = this.parseFilename(response.headers.get('content-disposition'))
                    || I18nManager.t('organize.records.fallback_filename');
                this.triggerDownload(blob, filename);
                onSuccess(filename);
            })
            .catch(err => onError((err && err.message) || I18nManager.t('common.network_error')));
    },

    /**
     * @description 用途说明：从 Content-Disposition 响应头解析下载文件名（优先 RFC 5987 filename* 编码）
     * @param {string} disposition - 入参说明：Content-Disposition 响应头原始值，可为 null
     * @returns {string} - 返回值说明：解析出的文件名，解析失败返回空串
     */
    parseFilename(disposition) {
        if (!disposition) return '';
        const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8Match) {
            try { return decodeURIComponent(utf8Match[1].trim()); } catch (e) { /* 编码异常时继续尝试普通 filename */ }
        }
        const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
        return plainMatch ? plainMatch[1].trim() : '';
    },

    /**
     * @description 用途说明：通过 Blob 与临时锚点触发浏览器下载，并在完成后释放临时 URL
     * @param {Blob} blob - 入参说明：CSV 文件内容 Blob
     * @param {string} filename - 入参说明：下载保存的文件名
     * @returns {void} - 返回值说明：无
     */
    triggerDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
};