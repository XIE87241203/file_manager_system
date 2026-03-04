/**
 * @description 前端多语言管理工具 (Module Pattern)
 */
const I18nManager = {
    /**
     * @description 当前加载的语言资源
     * @type {Object}
     */
    resources: {},

    /**
     * @description 当前语言标识
     * @type {string}
     */
    currentLang: 'en',

    /**
     * @description 用途说明：初始化多语言配置。优先级：URL 参数 > 传入参数 > localStorage > 默认 en。
     * @param {string} lang - 入参说明：语言标识 ('zh' 或 'en')。
     * @returns {void} - 返回值说明：无。
     */
    init: function(lang) {
        // 1. 尝试从 URL 获取 lang 参数
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');

        // 2. 确定最终语言标识
        this.currentLang = urlLang || lang || localStorage.getItem('sys_lang') || 'en';

        // 3. 持久化存储，方便后续页面读取
        localStorage.setItem('sys_lang', this.currentLang);

        // 4. 根据语言标识选择资源包
        if (this.currentLang === 'zh') {
            this.resources = typeof I18nZh !== 'undefined' ? I18nZh : {};
        } else {
            this.resources = typeof I18nEn !== 'undefined' ? I18nEn : {};
        }

        // 5. 设置 HTML 根节点的 lang 属性
        document.documentElement.lang = this.currentLang === 'zh' ? 'zh-CN' : 'en';
    },

    /**
     * @description 用途说明：根据键值路径获取翻译文案，并支持占位符替换（类似后端 kwargs）。
     * @param {string} key - 入参说明：键值路径，如 'common.save'。
     * @param {Object} params - 入参说明：可选，用于替换文案中 {key} 格式的占位符。
     * @returns {string} - 返回值说明：翻译后的文案，若找不到则返回 key 本身。
     */
    t: function(key, params = {}) {
        if (!key) return '';

        const keys = key.split('.');
        let result = this.resources;

        for (const k of keys) {
            if (result && result.hasOwnProperty(k)) {
                result = result[k];
            } else {
                result = null;
                break;
            }
        }

        let text = result || key;

        // 占位符替换逻辑，支持 {name} 格式
        if (params && typeof params === 'object') {
            Object.keys(params).forEach(pKey => {
                const placeholder = `{${pKey}}`;
                // 使用 split/join 实现全局替换
                text = text.split(placeholder).join(params[pKey]);
            });
        }

        return text;
    },

    /**
     * @description 用途说明：显式渲染页面中的国际化元素，支持 innerText, placeholder, title, value 四种属性。
     * @param {HTMLElement} container - 入参说明：待扫描的容器元素，默认为 document。
     * @returns {void} - 返回值说明：无。
     */
    render: function(container = document) {
        // 1. 处理主内容 (innerText) -> 对应 data-i18n
        container.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            el.innerText = this.t(key);
        });

        // 2. 处理占位符 (placeholder) -> 对应 data-i18n-placeholder
        container.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = this.t(key);
        });

        // 3. 处理悬浮提示 (title) -> 对应 data-i18n-title
        container.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = this.t(key);
        });

        // 4. 处理按钮/输入值 (value) -> 对应 data-i18n-value
        container.querySelectorAll('[data-i18n-value]').forEach(el => {
            const key = el.getAttribute('data-i18n-value');
            el.value = this.t(key);
        });
    }
};
