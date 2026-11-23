/**
 * 用途说明：相册浏览页面 API 请求封装，统一处理列表查询、缩略图生成、删除与媒体地址构建。
 * 每个业务方法均提供成功回调 (onSuccess) 与错误回调 (onError)。
 */
const AlbumBrowseRequest = {
    /**
     * 用途说明：构建带 Token 与仓库上下文的查询串（用于 img/video/a 标签直接访问）。
     * 入参说明：无
     * 返回值说明：string - 形如 &token=xxx&repo_id=1 的查询片段。
     */
    buildAuthQuery() {
        const token = Request.getCookie('token') || '';
        const repoId = typeof RepoContext !== 'undefined' ? RepoContext.get() : 1;
        return `&token=${encodeURIComponent(token)}&repo_id=${encodeURIComponent(repoId)}`;
    },

    /**
     * 用途说明：构建缩略图访问地址。
     * 入参说明：thumbPath (string) - 缩略图物理路径。
     * 返回值说明：string - 可直接用于 img.src 的地址。
     */
    buildThumbnailUrl(thumbPath) {
        return `/api/file_repository/thumbnail/view?path=${encodeURIComponent(thumbPath)}${this.buildAuthQuery()}`;
    },

    /**
     * 用途说明：构建原始媒体预览地址。
     * 入参说明：filePath (string) - 媒体文件完整路径。
     * 返回值说明：string - 可直接用于 img/video src 的地址。
     */
    buildMediaUrl(filePath) {
        return `/api/album/media?path=${encodeURIComponent(filePath)}${this.buildAuthQuery()}`;
    },

    /**
     * 用途说明：构建媒体下载地址。
     * 入参说明：filePath (string) - 媒体文件完整路径。
     * 返回值说明：string - 可直接用于 a.href 的下载地址。
     */
    buildDownloadUrl(filePath) {
        return `/api/album/download?path=${encodeURIComponent(filePath)}${this.buildAuthQuery()}`;
    },

    /**
     * 用途说明：分页获取相册媒体列表。
     * 入参说明：
     *   params (Object) - { page, limit, search, sort_by, order_asc }
     *   onSuccess (Function) - 成功回调，参数为分页结果对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    list(params, onSuccess, onError) {
        const query = new URLSearchParams({
            page: String(params.page || 1),
            limit: String(params.limit || 30),
            search: params.search || '',
            sort_by: params.sort_by || 'scan_time',
            order_asc: params.order_asc ? 'true' : 'false'
        });
        Request.get(`/api/album/list?${query.toString()}`, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res.data);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    },

    /**
     * 用途说明：按需为指定媒体生成缩略图（调用统一的缩略图生成接口）。
     * 入参说明：
     *   filePath (string) - 媒体文件完整路径。
     *   onSuccess (Function) - 成功回调，参数为 {file_path, thumbnail_path}。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
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
     * 用途说明：将指定文件批量移入回收站（仅标记，不删除物理文件）。
     * 入参说明：
     *   filePaths (Array<string>) - 媒体文件完整路径列表。
     *   onSuccess (Function) - 成功回调，参数为响应对象。
     *   onError (Function) - 失败回调，参数为错误信息。
     * 返回值说明：无
     */
    moveToRecycleBin(filePaths, onSuccess, onError) {
        Request.post('/api/file_repository/move_to_recycle_bin', { file_paths: filePaths }, {}, false)
            .then(res => {
                if (res.status === 'success') onSuccess(res);
                else onError(res.message);
            })
            .catch(err => onError(err.message || I18nManager.t('common.network_error')));
    }
};