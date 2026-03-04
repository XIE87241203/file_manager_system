/**
 * @description 任务进度状态枚举，与后端 ProgressStatus 对应
 */
const ProgressStatus = {
    IDLE: 'idle',
    PROCESSING: 'processing',
    COMPLETED: 'completed',
    ERROR: 'error'
};

/**
 * @description 通用 UI 组件库，封装可复用的页面元素及交互逻辑
 */
const UIComponents = {
    _previewPopover: null,

    /**
     * @description 用途说明：将 Date 对象格式化为 YYYY-MM-DD HH:mm:ss 字符串
     * @param {Date} date - 入参说明：需要格式化的日期对象，默认为当前时间
     * @returns {string} - 返回值说明：格式化后的日期时间字符串
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

    /**
     * @description 用途说明：从路径中提取文件名
     * @param {string} path - 入参说明：文件路径
     * @returns {string} - 返回值说明：提取出的文件名
     */
    getFileName(path) {
        if (!path) return '';
        const parts = path.split(/[/\\]/);
        return parts.pop() || '';
    },

    /**
     * @description 用途说明：更新表头排序状态的 UI
     * @param {NodeList} headers - 入参说明：表头元素集合
     * @param {string} field - 入参说明：当前排序字段
     * @param {string} order - 入参说明：排序方式 ('ASC' 或 'DESC')
     * @returns {void} - 返回值说明：无
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
     * @description 用途说明：获取表格空数据的占位 HTML
     * @param {number} colspan - 入参说明：合并单元格数量
     * @param {string} message - 入参说明：提示信息，若为空则使用多语言默认文案
     * @returns {string} - 返回值说明：表格行 HTML 字符串
     */
    getEmptyTableHtml(colspan, message) {
        const displayMsg = message || (typeof I18nManager !== 'undefined' ? I18nManager.t('common.no_data') : '');
        return `<tr><td colspan="${colspan}" style="text-align:center; padding: 100px; color: #9aa0a6;">${displayMsg}</td></tr>`;
    },

    /**
     * @description 用途说明：封装通用的表格行选中及全选逻辑
     * @param {Object} config - 入参说明：配置对象，包含 tableBody, selectAllCheckbox, selectedSet, onSelectionChange
     * @returns {void} - 返回值说明：无
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

    /**
     * @description 用途说明：显示全屏进度条遮罩
     * @param {string} parentSelector - 入参说明：父容器选择器
     * @param {string} initialText - 入参说明：初始显示的文字
     * @returns {void} - 返回值说明：无
     */
    showProgressBar(parentSelector, initialText) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;

        const defaultText = initialText || (typeof I18nManager !== 'undefined' ? I18nManager.t('common.processing') : '');

        let overlay = parent.querySelector('.common-progress-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'common-progress-overlay';
            overlay.innerHTML = `
                <div class="common-progress-card">
                    <div class="common-progress-spinner"></div>
                    <span class="common-progress-text">${defaultText}</span>
                    <div class="common-progress-bar-bg">
                        <div class="common-progress-bar-fill" style="width: 0%;"></div>
                    </div>
                </div>
            `;
            parent.appendChild(overlay);
        } else {
            this.updateProgressBar(parentSelector, 0, defaultText);
        }
    },

    /**
     * @description 用途说明：根据进度对象渲染进度条信息
     * @param {string} parentSelector - 入参说明：父容器的选择器
     * @param {Object} progress - 入参说明：进度对象，包含 current, total, message
     * @returns {void} - 返回值说明：无
     */
    renderProgress(parentSelector, progress) {
        if (!progress) return;
        const current = progress.current || 0;
        const total = progress.total || 0;
        const percent = total > 0 ? Math.round((current / total) * 100) : 0;
        const message = progress.message || '';
        
        let text = message;
        if (total > 0) {
            if (typeof I18nManager !== 'undefined') {
                text = I18nManager.t('common.progress_text', {
                    percent: percent,
                    current: current,
                    total: total,
                    msg: message
                });
            }
        }
        
        this.updateProgressBar(parentSelector, percent, text);
    },

    /**
     * @description 用途说明：直接更新进度条百分比和文字
     * @param {string} parentSelector - 入参说明：父容器选择器
     * @param {number} percent - 入参说明：进度百分比 (0-100)
     * @param {string} text - 入参说明：显示的文字
     * @returns {void} - 返回值说明：无
     */
    updateProgressBar(parentSelector, percent, text) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;
        let fill = parent.querySelector('.common-progress-bar-fill');
        let textEl = parent.querySelector('.common-progress-text');
        if (fill) fill.style.width = percent + '%';
        if (textEl && text) textEl.textContent = text;
    },

    /**
     * @description 用途说明：隐藏进度条遮罩
     * @param {string} parentSelector - 入参说明：父容器选择器
     * @returns {void} - 返回值说明：无
     */
    hideProgressBar(parentSelector) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;
        let overlay = parent.querySelector('.common-progress-overlay');
        if (overlay) overlay.style.display = 'none';
    },

    /**
     * @description 用途说明：弹出通用确认对话框
     * @param {Object} options - 入参说明：配置项，包含 title, message, confirmText, cancelText, checkbox, onConfirm, onCancel
     * @returns {void} - 返回值说明：无
     */
    showConfirmModal(options) {
        const t = (key) => (typeof I18nManager !== 'undefined' ? I18nManager.t(key) : '');

        const {
            title = t('common.hint'),
            message,
            confirmText = t('common.confirm'),
            cancelText = t('common.cancel'),
            checkbox,
            onConfirm,
            onCancel
        } = options;

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
     * @description 用途说明：弹出通用输入框弹窗
     * @param {Object} options - 入参说明：配置项，包含 title, placeholder, isTextArea, onConfirm, isSmall
     * @returns {void} - 返回值说明：无
     */
    showInputModal(options) {
        const t = (key) => (typeof I18nManager !== 'undefined' ? I18nManager.t(key) : '');

        const {
            title = t('common.hint'),
            placeholder = '',
            isTextArea = false,
            onConfirm,
            isSmall = false
        } = options;

        let modal = document.getElementById('common-input-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'common-input-modal';
            modal.className = 'modal-mask hidden';
            document.body.appendChild(modal);
        }

        const inputHtml = isTextArea
            ? `<textarea id="common-modal-input" class="input-field modal-input-textarea" placeholder="${placeholder}"></textarea>`
            : `<input type="text" id="common-modal-input" class="input-field" placeholder="${placeholder}">`;

        const contentClass = isSmall ? 'modal-content' : 'modal-content modal-input-content';

        modal.innerHTML = `
            <div class="${contentClass}">
                <h3 class="title">${title}</h3>
                <div class="form-group modal-input-group">
                    ${inputHtml}
                </div>
                <div class="flex-gap-5">
                    <button id="common-modal-input-confirm-btn" class="btn-primary mt-0 flex-1">${t('common.confirm')}</button>
                    <button id="common-modal-input-cancel-btn" class="btn-secondary mt-0 flex-1">${t('common.cancel')}</button>
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

    /**
     * @description 用途说明：初始化快速预览气泡
     * @returns {void} - 返回值说明：无
     */
    initQuickPreview() {
        if (this._previewPopover) return;
        this._previewPopover = document.createElement('div');
        this._previewPopover.className = 'quick-preview-popover';
        document.body.appendChild(this._previewPopover);
    },

    /**
     * @description 用途说明：显示快速预览图片
     * @param {Event} e - 入参说明：鼠标事件对象
     * @param {string} thumbPath - 入参说明：缩略图路径
     * @returns {void} - 返回值说明：无
     */
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

    /**
     * @description 用途说明：跟随鼠标移动预览气泡
     * @param {Event} e - 入参说明：鼠标事件对象
     * @returns {void} - 返回值说明：无
     */
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

    /**
     * @description 用途说明：隐藏快速预览图片
     * @returns {void} - 返回值说明：无
     */
    hideQuickPreview() {
        if (this._previewPopover) {
            this._previewPopover.style.display = 'none';
        }
    }
};
