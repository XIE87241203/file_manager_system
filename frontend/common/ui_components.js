/**
 * 用途说明：通用 UI 组件库，封装可复用的页面元素
 */
const UIComponents = {
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
     * 用途说明：更新进度条进度和文本
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
    }
};
