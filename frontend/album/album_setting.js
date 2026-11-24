/**
 * 用途说明：相册设置页逻辑，负责加载与保存缩略图存储路径，并展示解析后的实际目录。
 * 模块划分：State（状态）、UIController（DOM 操作）、API（接口封装）、App（入口）。
 */

// --- 状态管理 ---
const State = {
    configuredDir: '',
    effectiveDir: '',
    saving: false,
    // 缩略图同步任务状态（由系统设置迁入）
    thumbnailSync: {
        timer: null,
        widget: null,
        status: 'idle' // 记录同步任务的内部状态，初始为 idle
    }
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
    },

    /**
     * 用途说明：启动缩略图物理同步任务。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    startThumbnailSync(onSuccess, onError) {
        AlbumSettingRequest.startThumbnailSync(onSuccess, onError);
    },

    /**
     * 用途说明：停止缩略图物理同步任务。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    stopThumbnailSync(onSuccess, onError) {
        AlbumSettingRequest.stopThumbnailSync(onSuccess, onError);
    },

    /**
     * 用途说明：获取缩略图物理同步任务进度。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getThumbnailSyncProgress(onSuccess, onError) {
        AlbumSettingRequest.getThumbnailSyncProgress(onSuccess, onError);
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
    },

    /**
     * 用途说明：初始化缩略图同步按钮组件。
     * 入参说明：无
     * 返回值说明：无
     */
    initThumbnailSyncButton() {
        const container = document.getElementById('sync-thumbnail-btn-container');
        if (!container) return;

        State.thumbnailSync.widget = ProgressButtonWidget.create({
            normalText: I18nManager.t('album.sync_thumb'),
            stopText: I18nManager.t('common.cancel'),
            defaultBgColor: 'var(--color-primary-bootstrap)',
            onStart: () => App.handleStartThumbnailSync(),
            onStop: () => App.handleStopThumbnailSync()
        });

        container.appendChild(State.thumbnailSync.widget.getElement());
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
        UIController.initThumbnailSyncButton();
        this.bindEvents();
        this.loadSettings();
        // 初始化时检查一次同步任务状态
        this.syncThumbnailProgress();
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
    },

    /**
     * 用途说明：触发后端执行缩略图同步清理任务。
     * 入参说明：无
     * 返回值说明：无
     */
    handleStartThumbnailSync() {
        API.startThumbnailSync(
            () => {
                Toast.show(I18nManager.t('common.success'));
                this.syncThumbnailProgress();
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * 用途说明：触发后端停止当前正在进行的缩略图同步任务。
     * 入参说明：无
     * 返回值说明：无
     */
    handleStopThumbnailSync() {
        API.stopThumbnailSync(
            () => {
                Toast.show(I18nManager.t('common.success'));
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * 用途说明：异步获取缩略图同步进度，并根据状态更新 ProgressButtonWidget 的 UI 表现，支持自动轮询。
     * 入参说明：无
     * 返回值说明：无
     */
    syncThumbnailProgress() {
        if (State.thumbnailSync.timer) {
            clearTimeout(State.thumbnailSync.timer);
            State.thumbnailSync.timer = null;
        }

        API.getThumbnailSyncProgress(
            (data) => {
                const { status, progress } = data;
                const widget = State.thumbnailSync.widget;
                if (!widget) return;

                if (status === ProgressStatus.PROCESSING) {
                    State.thumbnailSync.status = ProgressStatus.PROCESSING;
                    widget.setState('processing');
                    const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
                    // 设置进度时同时设置文案，格式为：正在处理：当前/总数
                    widget.setProgress(percent, `${I18nManager.t('common.loading')}：${progress.current}/${progress.total}`);

                    // 继续轮询
                    State.thumbnailSync.timer = setTimeout(() => this.syncThumbnailProgress(), 1000);
                } else {
                    // 仅当之前的任务状态不是 idle 时（即刚从 processing 切换过来），才执行状态重置并弹出结果提示
                    if (State.thumbnailSync.status !== ProgressStatus.IDLE) {
                        if (status === ProgressStatus.COMPLETED) {
                            Toast.show(progress.message || I18nManager.t('common.success'));
                        } else if (status === ProgressStatus.ERROR) {
                            Toast.show(I18nManager.t('common.error') + ': ' + progress.message);
                        }
                        State.thumbnailSync.status = ProgressStatus.IDLE;
                    }
                    widget.setState('idle');
                }
            },
            (msg) => {
                console.error('获取进度失败:', msg);
                if (State.thumbnailSync.widget) {
                    State.thumbnailSync.widget.setState('idle');
                }
                State.thumbnailSync.status = ProgressStatus.IDLE;
            }
        );
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());