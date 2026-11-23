/**
 * 用途说明：相册设置页逻辑，负责加载与保存缩略图存储路径，并展示解析后的实际目录。
 * 模块划分：State（状态）、UIController（DOM 操作）、API（接口封装）、App（入口）。
 */

// --- 状态管理 ---
const State = {
    configuredDir: '',
    effectiveDir: '',
    saving: false
};

// --- API 封装 ---
const API = {
    /**
     * 用途说明：读取相册设置。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getSettings(onSuccess, onError) {
        AlbumSettingRequest.getSettings(onSuccess, onError);
    },

    /**
     * 用途说明：保存相册设置。
     * 入参说明：thumbnailDir (string) - 缩略图路径；onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    saveSettings(thumbnailDir, onSuccess, onError) {
        AlbumSettingRequest.updateSettings(thumbnailDir, onSuccess, onError);
    }
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化多语言与顶部栏，并缓存 DOM 元素。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        HeaderToolbar.init({
            title: I18nManager.t('album.setting_title'),
            backCallback: () => window.history.back(),
            showBack: true
        });

        this.elements = {
            dirInput: document.getElementById('thumbnail-dir-input'),
            effectiveValue: document.getElementById('thumbnail-dir-effective'),
            saveBtn: document.getElementById('btn-save-album-setting')
        };
    },

    /**
     * 用途说明：回填设置数据到界面。
     * 入参说明：data (Object) - {thumbnail_dir, thumbnail_dir_effective}。
     * 返回值说明：无
     */
    renderSettings(data) {
        if (!data) return;
        State.configuredDir = data.thumbnail_dir || '';
        State.effectiveDir = data.thumbnail_dir_effective || '';
        if (this.elements.dirInput) this.elements.dirInput.value = State.configuredDir;
        if (this.elements.effectiveValue) this.elements.effectiveValue.textContent = State.effectiveDir || '--';
    },

    /**
     * 用途说明：设置保存按钮的忙碌状态，避免重复提交。
     * 入参说明：saving (boolean) - 是否保存中。
     * 返回值说明：无
     */
    setSaving(saving) {
        State.saving = saving;
        if (this.elements.saveBtn) this.elements.saveBtn.disabled = saving;
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化页面并加载当前设置。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadSettings();
    },

    /**
     * 用途说明：绑定保存按钮事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const saveBtn = UIController.elements.saveBtn;
        if (saveBtn) saveBtn.onclick = () => this.saveSettings();
    },

    /**
     * 用途说明：加载相册设置。
     * 入参说明：无
     * 返回值说明：无
     */
    loadSettings() {
        API.getSettings((data) => {
            UIController.renderSettings(data);
        }, (msg) => {
            Toast.show(msg || I18nManager.t('album.settings_load_failed'));
        });
    },

    /**
     * 用途说明：校验并保存缩略图存储路径。
     * 入参说明：无
     * 返回值说明：无
     */
    saveSettings() {
        if (State.saving) return;
        const input = UIController.elements.dirInput;
        const value = (input ? input.value : '').trim();
        if (!value) {
            Toast.show(I18nManager.t('album.path_required'));
            return;
        }

        UIController.setSaving(true);
        API.saveSettings(value, (data) => {
            UIController.setSaving(false);
            UIController.renderSettings(data);
            Toast.show(I18nManager.t('album.save_success'));
        }, (msg) => {
            UIController.setSaving(false);
            Toast.show(msg || I18nManager.t('album.save_failed'));
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());