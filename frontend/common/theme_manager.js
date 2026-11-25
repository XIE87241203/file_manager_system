/**
 * 用途说明：管理页面主题偏好，在页面渲染前恢复上次选择，避免亮色主题闪烁。
 * 说明：仅支持 light / dark，选择保存在浏览器 localStorage 中。
 */
const ThemeManager = {
    /**
     * @description 用途说明：初始化主题，读取本地偏好并同步到根节点。
     * @returns {void} - 返回值说明：无。
     */
    init() {
        const savedTheme = this.getSavedTheme();
        this.applyTheme(savedTheme);
        document.addEventListener('DOMContentLoaded', () => this.updateControls());
    },

    /**
     * @description 用途说明：读取本地主题偏好，非法值回退到亮色主题。
     * @returns {string} - 返回值说明：light 或 dark。
     */
    getSavedTheme() {
        try {
            return localStorage.getItem('sys_theme') === 'dark' ? 'dark' : 'light';
        } catch (error) {
            return 'light';
        }
    },

    /**
     * @description 用途说明：应用指定主题并通知页面更新图标状态。
     * @param {string} theme - 入参说明：主题标识 light 或 dark。
     * @returns {void} - 返回值说明：无。
     */
    applyTheme(theme) {
        const nextTheme = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.theme = nextTheme;
        document.documentElement.style.colorScheme = nextTheme;
        try {
            localStorage.setItem('sys_theme', nextTheme);
        } catch (error) {
            // 浏览器禁用本地存储时仍允许当前页面切换主题。
        }
        this.updateControls();
        document.dispatchEvent(new CustomEvent('appearance:themechange', { detail: { theme: nextTheme } }));
    },

    /**
     * @description 用途说明：在亮色与暗色主题之间切换。
     * @returns {string} - 返回值说明：切换后的主题标识。
     */
    toggleTheme() {
        const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme(nextTheme);
        return nextTheme;
    },

    /**
     * @description 用途说明：更新主题按钮的提示文案与无障碍标签。
     * @returns {void} - 返回值说明：无。
     */
    updateControls() {
        const isDark = document.documentElement.dataset.theme === 'dark';
        const text = typeof I18nManager !== 'undefined'
            ? I18nManager.t(isDark ? 'common.switch_to_light' : 'common.switch_to_dark')
            : '';
        document.querySelectorAll('[data-appearance-theme-toggle], [data-theme-toggle]').forEach(button => {
            if (text) {
                button.title = text;
                button.setAttribute('aria-label', text);
            }
        });
    }
};

ThemeManager.init();
