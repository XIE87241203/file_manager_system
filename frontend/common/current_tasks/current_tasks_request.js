/**
 * 用途说明：当前任务中心请求封装，统一通过 Request 携带 Token 与仓库上下文。
 */
const CurrentTasksRequest = {
    /**
     * 用途说明：获取当前用户可见的全部运行或暂停任务。
     * 入参说明：onSuccess (Function) - 成功回调，接收任务列表响应；onError (Function) - 失败回调。
     * 返回值说明：无。
     */
    list(onSuccess, onError) {
        Request.get('/api/tasks/list', {}, false).then(onSuccess).catch(onError);
    },

    /**
     * 用途说明：请求暂停、恢复或停止指定仓库中的任务。
     * 入参说明：key (string) - 任务类型；repoId (number) - 仓库 ID；action (string) - pause/resume/stop；
     *           onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无。
     */
    control(key, repoId, action, onSuccess, onError) {
        Request.post('/api/tasks/control', { key, repo_id: repoId, action }, {}, false)
            .then(onSuccess).catch(onError);
    }
};
