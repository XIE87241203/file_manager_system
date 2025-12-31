/**
 * 用途说明：通用 UI 组件库，封装可复用的页面元素
 */
const UIComponents = {
    /**
     * 用途说明：初始化并渲染公用顶部工具栏
     * 入参说明：
     *   - title (str): 工具栏显示的标题文字
     *   - showBack (bool): 是否显示返回按钮，默认为 true
     *   - backUrl (str): 返回按钮跳转的自定义地址，若不传则默认执行 window.history.back()
     * 返回值说明：无
     */
    initHeader(title, showBack = true, backUrl = null) {
        // 1. 查找或创建 header 容器
        let header = document.querySelector('header.top-bar');
        if (!header) {
            header = document.createElement('header');
            header.className = 'top-bar';
            document.body.prepend(header);
        }

        // 2. 渲染内部 HTML 结构
        header.innerHTML = `
            <button id="nav-back-btn" class="back-btn" style="${showBack ? '' : 'visibility: hidden;'}">
                <span>&lt; 返回</span>
            </button>
            <div class="top-bar-title">${title}</div>
        `;

        // 3. 绑定返回按钮逻辑
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
    }
};
