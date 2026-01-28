/**
 * 用途说明：任务进度状态枚举，与后端 ProgressStatus 对应
 */
const ProgressStatus = {
    IDLE: 'idle',
    PROCESSING: 'processing',
    COMPLETED: 'completed',
    ERROR: 'error'
};

/**
 * 用途说明：通用 UI 组件库，封装可复用的页面元素及交互逻辑
 */
const UIComponents = {
    _previewPopover: null,

    /**
     * 用途说明：初始化并渲染公用顶部工具栏，并自动处理页面内容避让
     */
    initHeader(title, showBack = true, backUrl = null, rightBtnText = null, rightBtnCallback = null, rightBtnClass = 'right-btn') {
        let header = document.querySelector('header.top-bar');
        if (!header) {
            header = document.createElement('header');
            header.className = 'top-bar';
            document.body.prepend(header);
        }

        header.innerHTML = `
            <div class="top-bar-left">
                <button id="nav-back-btn" class="back-btn" style="${showBack ? '' : 'visibility: hidden;'}">
                    <span>&lt; 返回</span>
                </button>
            </div>
            <div class="top-bar-title">${title}</div>
            <div class="top-bar-right">
                ${rightBtnText ? `<button id="nav-right-btn" class="${rightBtnClass}">${rightBtnText}</button>` : ''}
            </div>
        `;

        document.body.style.boxSizing = 'border-box';

        if (showBack) {
            const backBtn = document.getElementById('nav-back-btn');
            if (backBtn) {
                backBtn.onclick = () => {
                    if (backUrl) window.location.href = backUrl;
                    else window.history.back();
                };
            }
        }

        if (rightBtnText && rightBtnCallback) {
            const rightBtn = document.getElementById('nav-right-btn');
            if (rightBtn) rightBtn.onclick = rightBtnCallback;
        }
    },

    /**
     * 用途说明：初始化仓库类型页面的顶部工具栏（含搜索框、返回、可选右侧按钮、可选历史库勾选）
     * 入参说明：
     *   - config (object): {
     *       searchPlaceholder: str,
     *       showHistoryCheckbox: bool,
     *       rightBtnText: str,
     *       rightBtnId: str, // 右侧按钮 ID，默认为 btn-right-action
     *       onSearch: func, // 点击搜索或回车时的回调
     *       onHistoryChange: func // 历史库勾选变化时的回调
     *     }
     */
    initRepoHeader(config) {
        const { 
            searchPlaceholder = '搜索...', 
            showHistoryCheckbox = false, 
            rightBtnText = null, 
            rightBtnId = 'btn-right-action',
            onSearch = null,
            onHistoryChange = null
        } = config;

        let header = document.querySelector('header.top-bar');
        if (!header) {
            header = document.createElement('header');
            header.className = 'top-bar';
            document.body.prepend(header);
        }

        const historyHtml = showHistoryCheckbox ? `
            <div class="search-section">
                <label class="checkbox-label">
                    <input type="checkbox" id="search-history-checkbox" class="checkbox-input"> 搜索历史库
                </label>
            </div>
        ` : '';

        const rightBtnHtml = rightBtnText ? `<button id="${rightBtnId}" class="right-btn">${rightBtnText}</button>` : '';

        header.innerHTML = `
            <div class="top-bar-left">
                <button id="nav-back-btn" class="back-btn" title="返回上一页">
                    <span>&lt; 返回</span>
                </button>
            </div>
            <div class="top-bar-center">
                <div class="search-container">
                    <input type="text" id="search-input" class="search-input" placeholder="${searchPlaceholder}" autocomplete="off">
                    <button id="search-btn" class="search-btn" title="点击搜索">
                        <i class="search-icon"></i>
                    </button>
                </div>
                ${historyHtml}
            </div>
            <div class="top-bar-right">
                ${rightBtnHtml}
            </div>
        `;

        // 绑定事件
        const backBtn = document.getElementById('nav-back-btn');
        if (backBtn) backBtn.onclick = () => window.history.back();

        const searchInput = document.getElementById('search-input');
        const searchBtn = document.getElementById('search-btn');
        if (onSearch) {
            if (searchBtn) searchBtn.onclick = onSearch;
            if (searchInput) {
                searchInput.onkeypress = (e) => {
                    if (e.key === 'Enter') onSearch();
                };
            }
        }

        if (showHistoryCheckbox && onHistoryChange) {
            const historyCheckbox = document.getElementById('search-history-checkbox');
            if (historyCheckbox) historyCheckbox.onchange = onHistoryChange;
        }

        document.body.style.boxSizing = 'border-box';
    },

    /**
     * 用途说明：将 Date 对象格式化为 YYYY-MM-DD HH:mm:ss 字符串
     * 入参说明：date (Date): 需要格式化的日期对象，默认为当前时间
     * 返回值说明：str - 格式化后的字符串
     */
    formatDate(date = new Date()) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        const hh = String(date.getHours()).padStart(2, '0');
        const mm = String(date.getMinutes()).padStart(2, '0');
        const ss = String(date.getSeconds()).padStart(2, '0');
        return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
    },

    getFileName(path) {
        if (!path) return '';
        const parts = path.split(/[/\\]/);
        return parts.pop() || '';
    },

    /**
     * 用途说明：更新表头排序状态的 UI
     * 入参说明：
     *   - headers (NodeList): 表头元素集合
     *   - field (str): 当前排序字段
     *   - order (str): 'ASC' 或 'DESC'
     */
    updateSortUI(headers, field, order) {
        headers.forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
            if (th.getAttribute('data-field') === field) {
                th.classList.add(order === 'ASC' ? 'sort-asc' : 'sort-desc');
            }
        });
    },

    /**
     * 用途说明：获取表格空数据的占位 HTML
     * 入参说明：
     *   - colspan (number): 合并单元格数量
     *   - message (str): 提示信息
     * 返回值说明：str - 表格行 HTML 字符串
     */
    getEmptyTableHtml(colspan, message = '暂无数据') {
        return `<tr><td colspan="${colspan}" style="text-align:center; padding: 100px; color: #9aa0a6;">${message}</td></tr>`;
    },

    /**
     * 用途说明：封装通用的表格行选中及全选逻辑
     * 入参说明：
     *   - config (object): {
     *       tableBody: HTMLElement,
     *       selectAllCheckbox: HTMLElement,
     *       selectedSet: Set, // 存储选中项 ID/Path 的集合
     *       onSelectionChange: (func) 选中项发生变化时的回调
     *     }
     */
    bindTableSelection(config) {
        const { tableBody, selectAllCheckbox, selectedSet, onSelectionChange } = config;
        if (!tableBody) return;

        // 1. 处理全选
        if (selectAllCheckbox) {
            selectAllCheckbox.onchange = (e) => {
                const isChecked = e.target.checked;
                const checkboxes = tableBody.querySelectorAll('.file-checkbox');
                checkboxes.forEach(cb => {
                    cb.checked = isChecked;
                    const id = cb.getAttribute('data-path') || cb.getAttribute('data-id');
                    const tr = cb.closest('tr');
                    if (isChecked) {
                        selectedSet.add(id);
                        if (tr) tr.classList.add('selected-row');
                    } else {
                        selectedSet.delete(id);
                        if (tr) tr.classList.remove('selected-row');
                    }
                });
                if (onSelectionChange) onSelectionChange(selectedSet.size);
            };
        }

        // 2. 处理行点击委托
        tableBody.onclick = (e) => {
            const tr = e.target.closest('tr');
            if (!tr) return;
            const checkbox = tr.querySelector('.file-checkbox');
            if (!checkbox) return;

            const id = checkbox.getAttribute('data-path') || checkbox.getAttribute('data-id');

            // 如果点击的不是 checkbox 本身，则切换它的状态
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
            }

            if (checkbox.checked) {
                selectedSet.add(id);
                tr.classList.add('selected-row');
            } else {
                selectedSet.delete(id);
                tr.classList.remove('selected-row');
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
            }

            if (onSelectionChange) onSelectionChange(selectedSet.size);
        };
    },

    showProgressBar(parentSelector, initialText = '正在处理...') {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;

        let overlay = parent.querySelector('.common-progress-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'common-progress-overlay';
            overlay.innerHTML = `
                <div class="common-progress-card">
                    <div class="common-progress-spinner"></div>
                    <span class="common-progress-text">${initialText}</span>
                    <div class="common-progress-bar-bg">
                        <div class="common-progress-bar-fill" style="width: 0%;"></div>
                    </div>
                </div>
            `;
            parent.appendChild(overlay);
        } else {
            this.updateProgressBar(parentSelector, 0, initialText);
        }
        overlay.style.display = 'flex';
    },

    /**
     * 用途说明：渲染进度条信息
     * 入参说明：
     *   - parentSelector (str): 父容器的选择器
     *   - progress (object): 进度对象，包含 current, total, message
     * 返回值说明：无
     */
    renderProgress(parentSelector, progress) {
        if (!progress) return;
        const current = progress.current || 0;
        const total = progress.total || 0;
        const percent = total > 0 ? Math.round((current / total) * 100) : 0;
        const message = progress.message || '';
        
        // 优化逻辑：如果总数为0，不显示具体的百分比和数值，只显示消息内容
        let text = message;
        if (total > 0) {
            text = `进度: ${percent}% (${current}/${total}) - ${message}`;
        }
        
        this.updateProgressBar(parentSelector, percent, text);
    },

    updateProgressBar(parentSelector, percent, text) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;
        let fill = parent.querySelector('.common-progress-bar-fill');
        let textEl = parent.querySelector('.common-progress-text');
        if (fill) fill.style.width = percent + '%';
        if (textEl && text) textEl.textContent = text;
    },

    hideProgressBar(parentSelector) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;
        let overlay = parent.querySelector('.common-progress-overlay');
        if (overlay) overlay.style.display = 'none';
    },

    showConfirmModal(options) {
        const { title = '确认操作', message, confirmText = '确定', cancelText = '取消', checkbox, onConfirm, onCancel } = options;
        let modal = document.getElementById('common-confirm-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'common-confirm-modal';
            modal.className = 'modal-mask hidden';
            document.body.appendChild(modal);
        }

        const checkboxHtml = checkbox ? `
            <div class="modal-checkbox-container">
                <input type="checkbox" id="common-modal-checkbox" ${checkbox.checked ? 'checked' : ''}>
                <label for="common-modal-checkbox">${checkbox.label}</label>
            </div>
        ` : '';

        modal.innerHTML = `
            <div class="modal-content">
                <h3 class="title">${title}</h3>
                <p class="modal-msg">${message}</p>
                ${checkboxHtml}
                <div class="flex-gap-5">
                    <button id="common-modal-confirm-btn" class="btn-danger mt-0 flex-1">${confirmText}</button>
                    <button id="common-modal-cancel-btn" class="btn-secondary mt-0 flex-1">${cancelText}</button>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
        const checkboxInput = document.getElementById('common-modal-checkbox');

        document.getElementById('common-modal-confirm-btn').onclick = () => {
            modal.classList.add('hidden');
            if (onConfirm) onConfirm(checkboxInput ? checkboxInput.checked : false);
        };

        document.getElementById('common-modal-cancel-btn').onclick = () => {
            modal.classList.add('hidden');
            if (onCancel) onCancel();
        };
    },

    /**
     * 用途说明：弹出通用输入框弹窗（如添加忽略文件）
     * 入参说明：options (object): { title, placeholder, isTextArea, onConfirm, isSmall }
     */
    showInputModal(options) {
        const { title = '输入内容', placeholder = '', isTextArea = false, onConfirm, isSmall = false } = options;
        let modal = document.getElementById('common-input-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'common-input-modal';
            modal.className = 'modal-mask hidden';
            document.body.appendChild(modal);
        }

        // 使用专门的类名 modal-input-textarea 来替换之前的内联 style，尺寸由 CSS 控制
        const inputHtml = isTextArea 
            ? `<textarea id="common-modal-input" class="input-field modal-input-textarea" placeholder="${placeholder}"></textarea>`
            : `<input type="text" id="common-modal-input" class="input-field" placeholder="${placeholder}">`;

        // 为 modal-content 添加了 modal-input-content 类，实现 70% 宽高的动态调整
        // 如果 isSmall 为 true，则不使用大尺寸类名
        const contentClass = isSmall ? 'modal-content' : 'modal-content modal-input-content';

        modal.innerHTML = `
            <div class="${contentClass}">
                <h3 class="title">${title}</h3>
                <div class="form-group modal-input-group">
                    ${inputHtml}
                </div>
                <div class="flex-gap-5">
                    <button id="common-modal-input-confirm-btn" class="btn-primary mt-0 flex-1">确定</button>
                    <button id="common-modal-input-cancel-btn" class="btn-secondary mt-0 flex-1">取消</button>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
        const inputEl = document.getElementById('common-modal-input');
        inputEl.focus();

        document.getElementById('common-modal-input-confirm-btn').onclick = () => {
            const value = inputEl.value.trim();
            if (onConfirm) onConfirm(value);
            modal.classList.add('hidden');
        };

        document.getElementById('common-modal-input-cancel-btn').onclick = () => {
            modal.classList.add('hidden');
        };

        // 支持回车确认（非 textarea 模式）
        if (!isTextArea) {
            inputEl.onkeypress = (e) => {
                if (e.key === 'Enter') {
                    const value = inputEl.value.trim();
                    if (onConfirm) onConfirm(value);
                    modal.classList.add('hidden');
                }
            };
        }
    },

    initQuickPreview() {
        if (this._previewPopover) return;
        this._previewPopover = document.createElement('div');
        this._previewPopover.className = 'quick-preview-popover';
        document.body.appendChild(this._previewPopover);
    },

    showQuickPreview(e, thumbPath) {
        if (!thumbPath) return;
        this.initQuickPreview();
        const apiBase = Request.baseUrl;
        const token = Request.getCookie('token');
        const imgUrl = `${apiBase}/api/file_repository/thumbnail/view?path=${encodeURIComponent(thumbPath)}&token=${token}`;
        this._previewPopover.innerHTML = `<img src="${imgUrl}" alt="预览图">`;
        this._previewPopover.style.display = 'block';
        this.moveQuickPreview(e);
    },

    moveQuickPreview(e) {
        if (!this._previewPopover || this._previewPopover.style.display === 'none') return;
        const offset = 20;
        let x = e.clientX + offset;
        let y = e.clientY + offset;
        const popoverRect = this._previewPopover.getBoundingClientRect();
        if (x + popoverRect.width > window.innerWidth) x = e.clientX - popoverRect.width - offset;
        if (y + popoverRect.height > window.innerHeight) y = e.clientY - popoverRect.height - offset;
        this._previewPopover.style.left = `${x}px`;
        this._previewPopover.style.top = `${y}px`;
    },

    hideQuickPreview() {
        if (this._previewPopover) {
            this._previewPopover.style.display = 'none';
            this._previewPopover.innerHTML = '';
        }
    },

    /**
     * 用途说明：内部方法：将滚动内容置顶
     */
    _scrollToTop() {
        // 尝试寻找项目常用的滚动容器
        const scrollContainers = ['.table-wrapper', '.repo-content-group', '#results-wrapper'];
        let scrolled = false;
        for (const selector of scrollContainers) {
            const el = document.querySelector(selector);
            if (el) {
                el.scrollTop = 0;
                scrolled = true;
            }
        }
        // 如果没找到局部容器或为了保险，同时也滚动 window
        window.scrollTo(0, 0);
    },

    /**
     * 用途说明：初始化分页组件
     * 入参说明：containerId (str) - 容器 ID，options (obj) - 配置项 { onPageChange, limit }
     * 返回值说明：返回包含 update 方法的控制器对象
     */
    initPagination(containerId, options) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        const { onPageChange, limit = 20 } = options;

        const render = (total, currentPage) => {
            const totalPages = Math.ceil(total / limit) || 1;
            container.style.display = 'flex';
            container.innerHTML = `
                <button class="btn-page" id="${containerId}-prev" ${currentPage <= 1 ? 'disabled' : ''}>上一页</button>
                <span class="page-info clickable-page-info" title="点击跳转页码">第 ${currentPage} / ${totalPages} 页 (共 ${total} 条)</span>
                <button class="btn-page" id="${containerId}-next" ${currentPage >= totalPages ? 'disabled' : ''}>下一页</button>
            `;

            const prevBtn = container.querySelector(`#${containerId}-prev`);
            const nextBtn = container.querySelector(`#${containerId}-next`);
            const pageInfo = container.querySelector('.page-info');

            if (prevBtn) prevBtn.onclick = () => {
                if (currentPage > 1) {
                    onPageChange(currentPage - 1);
                    this._scrollToTop();
                }
            };
            if (nextBtn) nextBtn.onclick = () => {
                if (currentPage < totalPages) {
                    onPageChange(currentPage + 1);
                    this._scrollToTop();
                }
            };

            if (pageInfo) {
                pageInfo.onclick = () => {
                    this.showInputModal({
                        title: '跳转页码',
                        placeholder: `请输入页码 (1-${totalPages})`,
                        isSmall: true,
                        onConfirm: (val) => {
                            const pageNum = parseInt(val);
                            if (isNaN(pageNum) || pageNum < 1 || pageNum > totalPages) {
                                Toast.show(`请输入 1 到 ${totalPages} 之间的有效页码`);
                                return;
                            }
                            if (pageNum === currentPage) return;
                            onPageChange(pageNum);
                            this._scrollToTop();
                        }
                    });
                };
            }
        };

        return {
            update: (total, currentPage) => render(total, currentPage)
        };
    }
};
