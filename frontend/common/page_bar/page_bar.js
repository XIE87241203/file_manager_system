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

        const t = (key, params) => (typeof I18nManager !== 'undefined' ? I18nManager.t(key, params) : '');

        // 格式化页面信息文案
        let infoText = `第 <b>${currentPage}</b> / <b>${totalPages}</b> 页 (共 <b>${totalItems}</b> 条)`;
        if (typeof I18nManager !== 'undefined') {
            infoText = I18nManager.t('common.page_info', {
                current: `<b>${currentPage}</b>`,
                total: `<b>${totalPages}</b>`,
                count: `<b>${totalItems}</b>`
            });
        }

        // 1. 生成 HTML 结构
        container.innerHTML = `
            <div class="page-bar-container">
                <div class="page-btn ${currentPage <= 1 ? 'disabled' : ''}" id="page-prev" title="${t('common.prev_page')}">
                    <img src="../../common/page_bar/prev_icon.svg" class="page-btn-icon">
                </div>
                <div class="page-info" id="page-jump" title="${t('common.jump_page_tip')}">
                    ${infoText}
                </div>
                <div class="page-btn ${currentPage >= totalPages ? 'disabled' : ''}" id="page-next" title="${t('common.next_page')}">
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

        const t = (key, params) => (typeof I18nManager !== 'undefined' ? I18nManager.t(key, params) : '');

        // 上一页逻辑
        if (prevBtn && !prevBtn.classList.contains('disabled')) {
            prevBtn.onclick = () => options.onPageChange(currentPage - 1);
        }

        // 下一页逻辑
        if (nextBtn && !nextBtn.classList.contains('disabled')) {
            nextBtn.onclick = () => options.onPageChange(currentPage + 1);
        }

        // 点击页码弹出输入框跳转
        if (jumpBtn) {
            jumpBtn.onclick = () => {
                const promptMsg = t('common.jump_page_prompt', { total: totalPages });
                const inputPage = prompt(promptMsg, currentPage);
                if (inputPage !== null) {
                    const pageNum = parseInt(inputPage);
                    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
                        if (pageNum !== currentPage) {
                            options.onPageChange(pageNum);
                        }
                    } else {
                        const errorMsg = t('common.jump_page_error', { total: totalPages });
                        if (typeof Toast !== 'undefined') {
                            Toast.show(errorMsg);
                        } else {
                            alert(errorMsg);
                        }
                    }
                }
            };
        }
    }
};
