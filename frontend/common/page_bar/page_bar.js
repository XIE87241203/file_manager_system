/**
 * 用途：分页栏组件封装，支持上一页、下一页、页码跳转和总数显示
 */
const PageBar = {
    /**
     * 初始化分页栏
     * @param {Object} options - 配置项
     * @param {string} options.containerId - 容器 ID
     * @param {number} options.totalItems - 总条目数
     * @param {number} options.pageSize - 每页显示条数
     * @param {number} options.currentPage - 当前页码 (从 1 开始)
     * @param {Function} options.onPageChange - 切换页面回调，参数为新的页码
     */
    init: function(options) {
        const container = document.getElementById(options.containerId);
        if (!container) {
            console.error(`未找到 ID 为 ${options.containerId} 的分页容器`);
            return;
        }

        const totalItems = options.totalItems || 0;
        const pageSize = options.pageSize || 20;
        const currentPage = options.currentPage || 1;
        const totalPages = Math.ceil(totalItems / pageSize) || 1;

        // 1. 生成 HTML 结构
        // 使用 disabled 类替代 hidden 类，实现变灰效果
        container.innerHTML = `
            <div class="page-bar-container">
                <div class="page-btn ${currentPage <= 1 ? 'disabled' : ''}" id="page-prev" title="上一页">
                    <img src="../../common/page_bar/prev_icon.svg" class="page-btn-icon">
                </div>
                <div class="page-info" id="page-jump" title="点击跳转页码">
                    第 <b>${currentPage}</b> / <b>${totalPages}</b> 页 (共 <b>${totalItems}</b> 条)
                </div>
                <div class="page-btn ${currentPage >= totalPages ? 'disabled' : ''}" id="page-next" title="下一页">
                    <img src="../../common/page_bar/next_icon.svg" class="page-btn-icon">
                </div>
            </div>
        `;

        // 2. 绑定事件
        this.bindEvents(options, totalPages);
    },

    /**
     * 绑定分页事件
     * @param {Object} options - 配置项
     * @param {number} totalPages - 总页数
     */
    bindEvents: function(options, totalPages) {
        const prevBtn = document.getElementById('page-prev');
        const nextBtn = document.getElementById('page-next');
        const jumpBtn = document.getElementById('page-jump');
        const currentPage = options.currentPage || 1;

        // 上一页逻辑：仅在非禁用状态下绑定
        if (prevBtn && !prevBtn.classList.contains('disabled')) {
            prevBtn.onclick = () => options.onPageChange(currentPage - 1);
        }

        // 下一页逻辑：仅在非禁用状态下绑定
        if (nextBtn && !nextBtn.classList.contains('disabled')) {
            nextBtn.onclick = () => options.onPageChange(currentPage + 1);
        }

        // 点击页码弹出输入框跳转
        if (jumpBtn) {
            jumpBtn.onclick = () => {
                const inputPage = prompt(`请输入要跳转的页码 (1 - ${totalPages}):`, currentPage);
                if (inputPage !== null) {
                    const pageNum = parseInt(inputPage);
                    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
                        if (pageNum !== currentPage) {
                            options.onPageChange(pageNum);
                        }
                    } else {
                        // 如果项目中集成了 Toast 建议替换，否则保留 alert 或 prompt 逻辑
                        if (typeof Toast !== 'undefined') {
                            Toast.show(`请输入 1 到 ${totalPages} 之间的有效页码`);
                        } else {
                            alert(`请输入 1 到 ${totalPages} 之间的有效页码`);
                        }
                    }
                }
            };
        }
    }
};
