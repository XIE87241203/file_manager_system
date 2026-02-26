/**
 * 用途：顶部工具栏逻辑封装，支持动态渲染和事件绑定
 */
const HeaderToolbar = {
    /**
     * 用途：初始化顶部工具栏
     * @param {Object} options - 配置项
     * @param {string} options.title - 工具栏标题
     * @param {boolean} [options.showBack=true] - 是否显示返回键，默认为 true。若为 false 则隐藏但保留占位。
     * @param {string} [options.menuIcon] - 右上角菜单图标路径，若不传则使用默认图标 "../../common/header_toolbar/icon/menu_icon.svg"
     * @param {Function} [options.backCallback] - 返回按钮点击回调，若不传则默认执行 window.history.back()
     * @param {Function} [options.menuCallback] - 菜单按钮点击回调，若不传则隐藏菜单图标但保留占位
     * @returns {void}
     */
    init: function(options) {
        console.log("HeaderToolbar 模块初始化...");
        const header = document.querySelector('.header-bar');
        if (!header) {
            console.error("未找到 class 为 'header-bar' 的 header 元素");
            return;
        }

        const title = options.title || "未命名页面";
        const showBack = options.showBack !== false; // 默认显示
        const hasMenu = typeof options.menuCallback === 'function';
        const menuIcon = options.menuIcon || "../../common/header_toolbar/icon/menu_icon.svg";

        // 1. 动态生成 HTML 结构
        header.innerHTML = `
            <div class="header-left">
                <div class="icon-btn" id="btn-back" title="返回" style="visibility: ${showBack ? 'visible' : 'hidden'}">
                    <img src="../../common/header_toolbar/icon/back_icon.svg" alt="返回" class="icon-img">
                </div>
            </div>
            <div class="header-title">${title}</div>
            <div class="header-right">
                <div class="icon-btn" id="btn-menu" title="菜单" style="visibility: ${hasMenu ? 'visible' : 'hidden'}">
                    <img src="${menuIcon}" alt="菜单" class="icon-img">
                </div>
            </div>
        `;

        // 2. 绑定事件
        this.bindEvents(options);
    },

    /**
     * 用途：绑定工具栏按钮事件
     * @param {Object} options - 配置项（同 init）
     * @returns {void}
     */
    bindEvents: function(options) {
        const backBtn = document.getElementById('btn-back');
        const menuBtn = document.getElementById('btn-menu');

        // 返回按钮逻辑
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                if (typeof options.backCallback === 'function') {
                    options.backCallback();
                } else {
                    window.history.back();
                }
            });
        }

        // 菜单按钮逻辑
        if (menuBtn && typeof options.menuCallback === 'function') {
            menuBtn.addEventListener('click', () => {
                options.menuCallback();
            });
        }
    }
};
