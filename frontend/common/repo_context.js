/**
 * 用途说明：仓库上下文工具，负责在浏览器本地持久化当前选中的仓库 ID，
 * 供 Request 在每次请求时通过 X-Repo-Id 请求头携带，实现多仓库数据隔离。
 */
const RepoContext = {
    /** 本地存储键名 */
    STORAGE_KEY: 'currentRepoId',
    /** 默认仓库 ID（项目初始化时创建） */
    DEFAULT_REPO_ID: 1,

    /**
     * 用途说明：获取当前仓库 ID。
     * 入参说明：无
     * 返回值说明：number - 当前仓库 ID，未设置或非法时返回默认仓库 ID。
     */
    get() {
        const raw = localStorage.getItem(this.STORAGE_KEY);
        const id = parseInt(raw, 10);
        return Number.isInteger(id) && id > 0 ? id : this.DEFAULT_REPO_ID;
    },

    /**
     * 用途说明：设置当前仓库 ID 并持久化。
     * 入参说明：id (number) - 仓库 ID。
     * 返回值说明：无
     */
    set(id) {
        const parsed = parseInt(id, 10);
        if (Number.isInteger(parsed) && parsed > 0) {
            localStorage.setItem(this.STORAGE_KEY, String(parsed));
        }
    },

    /**
     * 用途说明：清除当前仓库 ID（恢复为默认仓库）。
     * 入参说明：无
     * 返回值说明：无
     */
    clear() {
        localStorage.removeItem(this.STORAGE_KEY);
    }
};