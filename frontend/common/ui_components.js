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
 * 用途说明：通用 UI 组件库，封装可复用的页面元素
 */
const UIComponents = {
    _previewPopover: null,

    /**
     * 用途说明：初始化并渲染公用顶部工具栏，并自动处理页面内容避让
     * 入参说明：
     *   - title (str): 工具栏显示的标题文字
     *   - showBack (bool): 是否显示返回按钮，默认为 true
     *   - backUrl (str): 返回按钮跳转的自定义地址，若不传则默认执行 window.history.back()
     *   - rightBtnText (str): 右侧按钮显示的文字，如果不传则不显示
     *   - rightBtnCallback (func): 右侧按钮点击的回调函数
     *   - rightBtnClass (str): 右侧按钮的自定义 CSS 类名，默认为 'right-btn'
     * 返回值说明：无
     */
    initHeader(title, showBack = true, backUrl = null, rightBtnText = null, rightBtnCallback = null, rightBtnClass = 'right-btn') {
        // 1. 查找或创建 header 容器
        let header = document.querySelector('header.top-bar');
        if (!header) {
            header = document.createElement('header');
            header.className = 'top-bar';
            document.body.prepend(header);
        }

        // 2. 渲染内部 HTML 结构 (适配 common.css 中的左、中、右三段式布局)
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

        // 3. 避开头部高度：通过 JS 动态设置 body 的 paddingTop，确保内容不被固定定位的 header 遮挡
        // 统一处理高度为 60px，不再依赖 CSS 中的各类 margin-top 避让
        document.body.style.paddingTop = this.getToolbarHeight() + 'px';
        document.body.style.boxSizing = 'border-box';

        // 4. 绑定返回按钮逻辑
        if (showBack) {
            const backBtn = document.getElementById('nav-back-btn');
            if (backBtn) {
                backBtn.onclick = () => {
                    if (backUrl) {
                        window.location.href = backUrl;
                    } else {
                        window.history.back();
                    }
                };
            }
        }

        // 5. 绑定右侧按钮逻辑
        if (rightBtnText && rightBtnCallback) {
            const rightBtn = document.getElementById('nav-right-btn');
            if (rightBtn) {
                rightBtn.onclick = rightBtnCallback;
            }
        }
    },

    /**
     * 用途说明：获取顶部工具栏的高度
     * 入参说明：无
     * 返回值说明：Number - 工具栏高度（像素）
     */
    getToolbarHeight() {
        const header = document.querySelector('header.top-bar');
        // 如果 header 存在则返回其高度，否则返回预设的 60px
        return header ? header.offsetHeight || 60 : 60;
    },

    /**
     * 用途说明：显示并初始化进度条组件（如果已存在则重置状态）
     * 入参说明：
     *   - parentSelector (str): 进度条挂载的父容器选择器
     *   - initialText (str): 初始显示的文本内容
     * 返回值说明：无
     */
    showProgressBar(parentSelector, initialText = '正在处理...') {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;

        // 检查是否已存在，如果不存在则创建
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
            // 如果已存在，重置进度 and 文本
            this.updateProgressBar(parentSelector, 0, initialText);
        }
        overlay.style.display = 'flex';
    },

    /**
     * 用途说明：封装通用的进度更新逻辑，从后端进度对象中计算百分比并更新 UI
     * 入参说明：
     *   - parentSelector (str): 进度条所在的父容器选择器
     *   - progress (object): 后端返回的进度对象 (包含 current, total, message)
     * 返回值说明：无
     */
    renderProgress(parentSelector, progress) {
        if (!progress) return;
        const current = progress.current || 0;
        const total = progress.total || 0;
        const percent = total > 0 ? Math.round((current / total) * 100) : 0;
        const message = progress.message || '';
        
        // 统一进度文本格式
        const text = `进度: ${percent}% (${current}/${total}) - ${message}`;

        // 调用基础更新方法
        this.updateProgressBar(parentSelector, percent, text);
    },

    /**
     * 用途说明：更新进度条进度 and 文本
     * 入参说明：
     *   - parentSelector (str): 进度条所在的父容器选择器
     *   - percent (number): 进度百分比 (0-100)
     *   - text (str): 更新的文本内容
     * 返回值说明：无
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
     * 用途说明：隐藏进度条组件
     * 入参说明：
     *   - parentSelector (str): 进度条所在的父容器选择器
     * 返回值说明：无
     */
    hideProgressBar(parentSelector) {
        let parent = document.querySelector(parentSelector);
        if (!parent) return;

        let overlay = parent.querySelector('.common-progress-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    },

    /**
     * 用途说明：显示通用二次确认弹窗
     * 入参说明：
     *   - options (object): {
     *       title: (str) 标题,
     *       message: (str) 正文信息,
     *       confirmText: (str) 确认按钮文字,
     *       cancelText: (str) 取消按钮文字,
     *       checkbox: { label: (str), checked: (bool) } 可选复选框配置,
     *       onConfirm: (func) 点击确认的回调，入参为 checkbox 的状态,
     *       onCancel: (func) 点击取消的回调
     *     }
     * 返回值说明：无
     */
    showConfirmModal(options) {
        const { title = '确认操作', message, confirmText = '确定', cancelText = '取消', checkbox, onConfirm, onCancel } = options;
        
        // 查找或创建 modal 容器
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

        // 绑定事件
        const confirmBtn = document.getElementById('common-modal-confirm-btn');
        const cancelBtn = document.getElementById('common-modal-cancel-btn');
        const checkboxInput = document.getElementById('common-modal-checkbox');

        confirmBtn.onclick = () => {
            modal.classList.add('hidden');
            if (onConfirm) onConfirm(checkboxInput ? checkboxInput.checked : false);
        };

        cancelBtn.onclick = () => {
            modal.classList.add('hidden');
            if (onCancel) onCancel();
        };
    },

    /**
     * 用途说明：初始化快速预览组件
     * 入参说明：无
     * 返回值说明：无
     */
    initQuickPreview() {
        if (this._previewPopover) return;
        this._previewPopover = document.createElement('div');
        this._previewPopover.className = 'quick-preview-popover';
        document.body.appendChild(this._previewPopover);
    },

    /**
     * 用途说明：显示快速预览缩略图
     * 入参说明：
     *   - e (Event): 鼠标事件对象
     *   - thumbPath (str): 缩略图在服务端的物理路径
     * 返回值说明：无
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
     * 用途说明：随着鼠标移动更新预览窗口位置
     * 入参说明：
     *   - e (Event): 鼠标事件对象
     * 返回值说明：无
     */
    moveQuickPreview(e) {
        if (!this._previewPopover || this._previewPopover.style.display === 'none') return;
        
        const offset = 20;
        let x = e.clientX + offset;
        let y = e.clientY + offset;
        
        // 边界检查：防止预览窗超出屏幕
        const popoverRect = this._previewPopover.getBoundingClientRect();
        if (x + popoverRect.width > window.innerWidth) {
            x = e.clientX - popoverRect.width - offset;
        }
        if (y + popoverRect.height > window.innerHeight) {
            y = e.clientY - popoverRect.height - offset;
        }
        
        this._previewPopover.style.left = `${x}px`;
        this._previewPopover.style.top = `${y}px`;
    },

    /**
     * 用途说明：隐藏快速预览窗口
     * 入参说明：无
     * 返回值说明：无
     */
    hideQuickPreview() {
        if (this._previewPopover) {
            this._previewPopover.style.display = 'none';
            this._previewPopover.innerHTML = '';
        }
    }
};
