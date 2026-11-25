/**
 * @description 首页与登录页共用的外观控制组件，负责主题切换、语言切换弹窗及文案刷新。
 */
const AppearanceManager = {
    /**
     * @description 用途说明：绑定主题与语言按钮，并恢复控件提示文案。
     * @returns {void} - 返回值说明：无。
     */
    init() {
        document.querySelectorAll('[data-appearance-theme-toggle]').forEach(button => {
            button.onclick = () => ThemeManager.toggleTheme();
        });
        document.querySelectorAll('[data-appearance-language-open]').forEach(button => {
            button.onclick = () => this.showLanguageModal();
        });
        this.updateTexts();
    },

    /**
     * @description 用途说明：在指定容器中生成主题与语言切换按钮。
     * @param {string} containerId - 入参说明：按钮容器元素 ID。
     * @returns {void} - 返回值说明：无。
     */
    mount(containerId) {
        const container = document.getElementById(containerId);
        if (!container || container.children.length > 0) return;
        const themeButton = document.createElement('button');
        themeButton.type = 'button';
        themeButton.className = 'appearance-btn appearance-theme-btn';
        themeButton.dataset.appearanceThemeToggle = '';
        themeButton.innerHTML = '<span class="theme-icon appearance-sun icon-sun" aria-hidden="true"></span><span class="theme-icon appearance-moon icon-moon" aria-hidden="true"></span>';

        const languageButton = document.createElement('button');
        languageButton.type = 'button';
        languageButton.className = 'appearance-btn appearance-language-btn';
        languageButton.dataset.appearanceLanguageOpen = '';
        languageButton.innerHTML = '<span class="appearance-language-code" aria-hidden="true"></span>';
        container.append(themeButton, languageButton);
        this.init();
    },

    /**
     * @description 用途说明：显示语言选择弹窗，下拉框默认选中当前语言。
     * @returns {void} - 返回值说明：无。
     */
    showLanguageModal() {
        let modal = document.getElementById('appearance-language-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'appearance-language-modal';
            modal.className = 'modal-mask appearance-language-mask hidden';
            modal.innerHTML = `
                <div class="modal-content appearance-language-content" role="dialog" aria-modal="true" aria-labelledby="appearance-language-title">
                    <h3 id="appearance-language-title" class="title appearance-language-title"></h3>
                    <label for="appearance-language-select" class="appearance-language-label"></label>
                    <select id="appearance-language-select" class="input-field appearance-language-select"></select>
                    <div class="appearance-language-actions">
                        <button id="appearance-language-apply" type="button" class="btn-primary mt-0 flex-1"></button>
                        <button id="appearance-language-cancel" type="button" class="btn-secondary mt-0 flex-1"></button>
                    </div>
                </div>`;
            document.body.appendChild(modal);
        }

        const select = document.getElementById('appearance-language-select');
        select.innerHTML = '';
        [{ value: 'zh', key: 'common.language_zh' }, { value: 'en', key: 'common.language_en' }].forEach(option => {
            const element = document.createElement('option');
            element.value = option.value;
            element.textContent = I18nManager.t(option.key);
            select.appendChild(element);
        });
        select.value = I18nManager.currentLang === 'zh' ? 'zh' : 'en';
        this.updateModalTexts();
        modal.classList.remove('hidden');

        document.getElementById('appearance-language-apply').onclick = () => this.applyLanguage(select.value);
        document.getElementById('appearance-language-cancel').onclick = () => this.closeLanguageModal();
        modal.onclick = event => {
            if (event.target === modal) this.closeLanguageModal();
        };
        select.focus();
    },

    /**
     * @description 用途说明：应用选中语言，刷新页面静态文案并通知页面更新动态文案。
     * @param {string} language - 入参说明：语言标识 zh 或 en。
     * @returns {void} - 返回值说明：无。
     */
    applyLanguage(language) {
        I18nManager.init(language, true);
        I18nManager.render();
        this.closeLanguageModal();
        this.updateTexts();
        ThemeManager.updateControls();
        document.dispatchEvent(new CustomEvent('appearance:languagechange', { detail: { language: I18nManager.currentLang } }));
        Toast.show(I18nManager.t('common.language_applied'));
    },

    /**
     * @description 用途说明：关闭语言选择弹窗。
     * @returns {void} - 返回值说明：无。
     */
    closeLanguageModal() {
        const modal = document.getElementById('appearance-language-modal');
        if (modal) modal.classList.add('hidden');
    },

    /**
     * @description 用途说明：刷新主题按钮与语言按钮的提示文案。
     * @returns {void} - 返回值说明：无。
     */
    updateTexts() {
        document.querySelectorAll('[data-appearance-language-open]').forEach(button => {
            button.title = I18nManager.t('common.language_switch');
            button.setAttribute('aria-label', I18nManager.t('common.language_switch'));
            const code = button.querySelector('.appearance-language-code');
            if (code) {
                code.textContent = I18nManager.t(I18nManager.currentLang === 'zh' ? 'common.language_code_zh' : 'common.language_code_en');
            }
        });
        ThemeManager.updateControls();
        this.updateModalTexts();
    },

    /**
     * @description 用途说明：刷新已创建语言弹窗的标题、标签与按钮文案。
     * @returns {void} - 返回值说明：无。
     */
    updateModalTexts() {
        const title = document.getElementById('appearance-language-title');
        if (!title) return;
        title.textContent = I18nManager.t('common.language_title');
        document.querySelector('.appearance-language-label').textContent = I18nManager.t('common.language_label');
        document.getElementById('appearance-language-apply').textContent = I18nManager.t('common.language_apply');
        document.getElementById('appearance-language-cancel').textContent = I18nManager.t('common.cancel');
    }
};
