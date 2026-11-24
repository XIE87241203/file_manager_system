/**
 * 用途：搜索顶部工具栏逻辑封装，支持搜索输入、搜索按钮和事件绑定
 */
const SearchHeaderToolbar = {
    /**
     * 用途：初始化搜索顶部工具栏
     * @param {Object} options - 配置项
     * @param {string} options.searchHint - 搜索框提示文本
     * @param {boolean} [options.showBack=true] - 是否显示返回键，默认为 true。若为 false 则隐藏但保留占位。
     * @param {string} [options.theme="light"] - 主题风格，支持 "light" | "dark"，默认 light
     * @param {string} [options.menuIcon] - 右上角菜单图标路径，文件名需与亮色主题图标映射匹配
     * @param {Function} [options.backCallback] - 返回按钮点击回调，若不传则默认执行 window.history.back()
     * @param {Function} [options.menuCallback] - 菜单按钮点击回调，若不传则隐藏菜单图标但保留占位
     * @param {Function} options.searchCallback - 开始搜索回调，参数为搜索内容字符串
     * @returns {void}
     */
    init: function(options) {
        console.log("SearchHeaderToolbar 模块初始化...");
        const header = document.querySelector('.header-bar');
        if (!header) {
            console.error("未找到 class 为 'header-bar' 的 header 元素");
            return;
        }

        const hint = options.searchHint || "请输入搜索内容...";
        const showBack = options.showBack !== false; // 默认显示
        const hasMenu = typeof options.menuCallback === 'function';
        const menuIcon = options.menuIcon || "/common/themes/light/icons/menu_icon.svg";
        const menuIconMap = {
            'add_icon.svg': 'add',
            'menu_icon.svg': 'menu',
            'save_icon.svg': 'save',
            'search_icon.svg': 'search',
            'settings_icon.svg': 'settings',
            'export_icon.svg': 'export'
        };
        const menuIconName = menuIconMap[menuIcon.split('/').pop()] || 'menu';
        const themeClass = options.theme === 'dark' ? 'theme-dark' : 'theme-light';
        header.classList.remove('theme-dark', 'theme-light');
        header.classList.add(themeClass);

        // 1. 动态生成 HTML 结构
        header.innerHTML = `
            <div class="header-left">
                <div class="icon-btn" id="btn-back" title="返回" style="visibility: ${showBack ? 'visible' : 'hidden'}">
                    <span class="icon-img theme-icon icon-back" role="img" aria-label="返回"></span>
                </div>
            </div>
            <div class="search-input-container">
                <input type="text" id="search-input" class="search-input" placeholder="${hint}" autocomplete="off">
                <div class="search-action-btn" id="btn-search-trigger" title="搜索">
                    <span class="icon-img theme-icon icon-search" role="img" aria-label="搜索"></span>
                </div>
            </div>
            <div class="header-right">
                <div class="icon-btn" id="btn-menu" title="菜单" style="visibility: ${hasMenu ? 'visible' : 'hidden'}">
                    <span class="icon-img theme-icon icon-${menuIconName}" role="img" aria-label="菜单"></span>
                </div>
            </div>
        `;

        // 2. 绑定事件
        this.bindEvents(options);
    },

    /**
     * 用途：绑定工具栏按钮及搜索事件
     * @param {Object} options - 配置项（同 init）
     * @returns {void}
     */
    bindEvents: function(options) {
        const backBtn = document.getElementById('btn-back');
        const menuBtn = document.getElementById('btn-menu');
        const searchBtn = document.getElementById('btn-search-trigger');
        const searchInput = document.getElementById('search-input');

        // 执行搜索的内部辅助方法
        const performSearch = () => {
            if (typeof options.searchCallback === 'function' && searchInput) {
                const content = searchInput.value.trim();
                options.searchCallback(content);
            }
        };

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

        // 搜索按钮点击逻辑
        if (searchBtn) {
            searchBtn.addEventListener('click', performSearch);
        }

        // 搜索框回车逻辑
        if (searchInput) {
            searchInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    performSearch();
                }
            });
        }
    }
};
