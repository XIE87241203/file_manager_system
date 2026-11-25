/**
 * 用途说明：相册设置页逻辑，负责缩略图设置、缩略图同步与人脸识别任务的状态和操作。
 * 模块划分：State（状态）、UIController（DOM 操作）、API（接口封装）、App（入口）。
 */

// --- 状态管理 ---
const State = {
    configuredDir: '',
    effectiveDir: '',
    thumbnailSize: 256,
    autoFaceRecognition: false,
    thumbnailSizeOptions: [128, 256, 512, 1024, 2048],
    saving: false,
    // 缩略图同步任务状态（由系统设置迁入）
    thumbnailSync: {
        timer: null,
        widget: null,
        status: 'idle' // 记录同步任务的内部状态，初始为 idle
    },
    // 人脸识别独立轮询，避免与缩略图同步状态互相覆盖
    faceRecognition: {
        timer: null,
        status: 'idle',
        paused: false,
        pending: 0,
        remaining: 0,
        canManage: false,
        busy: false,
        lastStatus: null
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
     * 入参说明：thumbnailDir (string) - 缩略图路径；thumbnailSize (number) - 缩略图最大边长；
     *           autoFaceRecognition (boolean) - 自动识别新增图片开关；
     *           onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    saveSettings(thumbnailDir, thumbnailSize, autoFaceRecognition, onSuccess, onError) {
        AlbumSettingRequest.updateSettings(thumbnailDir, thumbnailSize, autoFaceRecognition, onSuccess, onError);
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
    },

    /**
     * 用途说明：读取当前用户信息。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getCurrentUser(onSuccess, onError) {
        AlbumSettingRequest.getCurrentUser(onSuccess, onError);
    },

    /**
     * 用途说明：读取人脸识别状态。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    getFaceStatus(onSuccess, onError) {
        AlbumSettingRequest.getFaceStatus(onSuccess, onError);
    },

    /**
     * 用途说明：启动人脸识别。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    startFaceRecognition(onSuccess, onError) {
        AlbumSettingRequest.startFaceRecognition(onSuccess, onError);
    },

    /**
     * 用途说明：暂停人脸识别，保留队列与已处理数据。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    pauseFaceRecognition(onSuccess, onError) {
        AlbumSettingRequest.pauseFaceRecognition(onSuccess, onError);
    },

    /**
     * 用途说明：停止人脸识别。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    stopFaceRecognition(onSuccess, onError) {
        AlbumSettingRequest.stopFaceRecognition(onSuccess, onError);
    },

    /**
     * 用途说明：停止识别并清除人脸数据。
     * 入参说明：onSuccess (Function) - 成功回调；onError (Function) - 失败回调。
     * 返回值说明：无
     */
    clearFaceRecognitionData(onSuccess, onError) {
        AlbumSettingRequest.clearFaceRecognitionData(onSuccess, onError);
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
            sizeSelect: document.getElementById('thumbnail-size-select'),
            effectiveValue: document.getElementById('thumbnail-dir-effective'),
            saveBtn: document.getElementById('btn-save-album-setting'),
            faceCard: document.getElementById('face-recognition-card'),
            autoFaceCheckbox: document.getElementById('auto-face-recognition'),
            faceStatusText: document.getElementById('face-status-text'),
            faceRemainingCount: document.getElementById('face-remaining-count'),
            faceSavedCount: document.getElementById('face-saved-count'),
            faceStartBtn: document.getElementById('btn-face-start'),
            facePauseBtn: document.getElementById('btn-face-pause'),
            faceStopBtn: document.getElementById('btn-face-stop'),
            faceClearBtn: document.getElementById('btn-face-clear')
        };
        this.renderThumbnailSizeOptions();
    },

    /**
     * 用途说明：回填设置数据到界面。
     * 入参说明：data (Object) - {thumbnail_dir, thumbnail_dir_effective, thumbnail_size, auto_face_recognition}。
     * 返回值说明：无
     */
    renderSettings(data) {
        if (!data) return;
        State.configuredDir = data.thumbnail_dir || '';
        State.effectiveDir = data.thumbnail_dir_effective || '';
        State.thumbnailSize = Number(data.thumbnail_size);
        State.autoFaceRecognition = data.auto_face_recognition === true;
        if (!Number.isInteger(State.thumbnailSize) || State.thumbnailSize <= 0) {
            State.thumbnailSize = 256;
        }
        if (this.elements.dirInput) this.elements.dirInput.value = State.configuredDir;
        if (this.elements.effectiveValue) this.elements.effectiveValue.textContent = State.effectiveDir || '--';
        if (this.elements.autoFaceCheckbox) {
            this.elements.autoFaceCheckbox.checked = State.autoFaceRecognition;
            this.elements.autoFaceCheckbox.disabled = !State.faceRecognition.canManage || State.saving;
        }
        this.renderThumbnailSizeOptions();
    },

    /**
     * 用途说明：生成缩略图分辨率选项，并保留旧配置中不在预设列表内的有效尺寸。
     * 入参说明：无
     * 返回值说明：无
     */
    renderThumbnailSizeOptions() {
        const select = this.elements.sizeSelect;
        if (!select) return;
        const sizes = State.thumbnailSizeOptions.slice();
        if (!sizes.includes(State.thumbnailSize)) sizes.push(State.thumbnailSize);
        sizes.sort((a, b) => a - b);
        select.innerHTML = '';
        sizes.forEach(size => {
            const option = document.createElement('option');
            option.value = String(size);
            option.textContent = I18nManager.t('album.thumbnail_size_option', { size });
            select.appendChild(option);
        });
        select.value = String(State.thumbnailSize);
    },

    /**
     * 用途说明：设置保存按钮的忙碌状态，避免重复提交。
     * 入参说明：saving (boolean) - 是否保存中。
     * 返回值说明：无
     */
    setSaving(saving) {
        State.saving = saving;
        if (this.elements.saveBtn) this.elements.saveBtn.disabled = saving;
        if (this.elements.autoFaceCheckbox) {
            this.elements.autoFaceCheckbox.disabled = saving || !State.faceRecognition.canManage;
        }
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
    },

    /**
     * 用途说明：根据当前用户是否为系统管理员显示或隐藏人脸识别卡片。
     * 入参说明：canManage (boolean) - 当前用户是否为系统管理员。
     * 返回值说明：无
     */
    applyFacePermission(canManage) {
        State.faceRecognition.canManage = canManage;
        if (this.elements.faceCard) {
            this.elements.faceCard.classList.toggle('hidden', !canManage);
        }
        if (this.elements.autoFaceCheckbox) {
            this.elements.autoFaceCheckbox.disabled = !canManage || State.saving;
        }
        if (State.faceRecognition.lastStatus) this.renderFaceStatus(State.faceRecognition.lastStatus);
    },

    /**
     * 用途说明：渲染人脸任务状态、剩余数量、已保存人脸数量和按钮可用状态。
     * 入参说明：data (Object) - 后端 FaceTaskStatusResult。
     * 返回值说明：无
     */
    renderFaceStatus(data) {
        if (!data) return;
        State.faceRecognition.lastStatus = data;
        State.faceRecognition.status = data.status || 'idle';
        State.faceRecognition.paused = data.paused === true || data.status === ProgressStatus.PAUSED;
        State.faceRecognition.pending = Number(data.pending) || 0;
        State.faceRecognition.remaining = Number(data.queued ?? data.remaining) || 0;

        let statusText = data.message || '--';
        const currentRepoId = typeof RepoContext !== 'undefined' ? RepoContext.get() : data.repo_id;
        const runningOtherRepo = Boolean(data.running && data.active_repo_id
            && Number(data.active_repo_id) !== Number(currentRepoId));
        if (runningOtherRepo) {
            statusText = I18nManager.t('album.face_running_other_repo', { id: data.active_repo_id });
        }
        if (this.elements.faceStatusText) this.elements.faceStatusText.textContent = statusText;
        if (this.elements.faceRemainingCount) {
            this.elements.faceRemainingCount.textContent = String(State.faceRecognition.remaining);
        }
        if (this.elements.faceSavedCount) {
            this.elements.faceSavedCount.textContent = String(Number(data.faces) || 0);
        }

        const running = Boolean(data.running);
        const runningCurrentRepo = running && !runningOtherRepo;
        const paused = State.faceRecognition.paused;
        const busy = State.faceRecognition.busy;
        const canManage = State.faceRecognition.canManage;
        if (this.elements.faceStartBtn) {
            this.elements.faceStartBtn.disabled = !canManage || busy || runningOtherRepo
                || (runningCurrentRepo && !paused)
                || (!running && State.faceRecognition.remaining <= 0
                    && State.faceRecognition.pending <= 0);
        }
        if (this.elements.facePauseBtn) {
            this.elements.facePauseBtn.disabled = !canManage || busy || !runningCurrentRepo || paused;
        }
        if (this.elements.faceStopBtn) {
            this.elements.faceStopBtn.disabled = !canManage || busy || runningOtherRepo
                || (!running && State.faceRecognition.remaining <= 0);
        }
        if (this.elements.faceClearBtn) {
            this.elements.faceClearBtn.disabled = !canManage || busy || runningOtherRepo;
        }
    },

    /**
     * 用途说明：设置人脸操作请求的忙碌状态，防止重复点击。
     * 入参说明：busy (boolean) - 是否正在请求后端。
     * 返回值说明：无
     */
    setFaceBusy(busy) {
        State.faceRecognition.busy = busy;
        if (State.faceRecognition.lastStatus) this.renderFaceStatus(State.faceRecognition.lastStatus);
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
        // 初始化时检查一次同步任务状态，并按权限加载人脸任务状态
        this.syncThumbnailProgress();
        this.loadCurrentUser();
    },

    /**
     * 用途说明：绑定相册设置保存与人脸识别操作事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const saveBtn = UIController.elements.saveBtn;
        if (saveBtn) saveBtn.onclick = () => this.saveSettings();
        if (UIController.elements.faceStartBtn) {
            UIController.elements.faceStartBtn.onclick = () => this.handleStartFaceRecognition();
        }
        if (UIController.elements.facePauseBtn) {
            UIController.elements.facePauseBtn.onclick = () => this.handlePauseFaceRecognition();
        }
        if (UIController.elements.faceStopBtn) {
            UIController.elements.faceStopBtn.onclick = () => this.handleStopFaceRecognition();
        }
        if (UIController.elements.faceClearBtn) {
            UIController.elements.faceClearBtn.onclick = () => this.confirmClearFaceData();
        }
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
     * 用途说明：校验并保存缩略图存储路径、最大边长与自动人脸识别开关。
     * 入参说明：无
     * 返回值说明：无
     */
    saveSettings() {
        if (State.saving) return;
        const input = UIController.elements.dirInput;
        const sizeSelect = UIController.elements.sizeSelect;
        const value = (input ? input.value : '').trim();
        const thumbnailSize = Number(sizeSelect ? sizeSelect.value : State.thumbnailSize);
        if (!value) {
            Toast.show(I18nManager.t('album.path_required'));
            return;
        }
        if (!Number.isInteger(thumbnailSize) || thumbnailSize <= 0) {
            Toast.show(I18nManager.t('album.thumbnail_size_invalid'));
            return;
        }

        UIController.setSaving(true);
        const autoFaceRecognition = State.faceRecognition.canManage
            ? Boolean(UIController.elements.autoFaceCheckbox && UIController.elements.autoFaceCheckbox.checked)
            : null;
        API.saveSettings(value, thumbnailSize, autoFaceRecognition, (data) => {
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
     * 用途说明：读取当前用户身份，仅系统管理员加载并显示人脸识别操作。
     * 入参说明：无
     * 返回值说明：无
     */
    loadCurrentUser() {
        API.getCurrentUser((data) => {
            UIController.applyFacePermission(data.is_admin === true);
            if (State.faceRecognition.canManage) this.refreshFaceStatus();
        }, (msg) => {
            UIController.applyFacePermission(false);
            Toast.show(msg || I18nManager.t('common.error'));
        });
    },

    /**
     * 用途说明：开始识别前二次确认；暂停恢复不重复弹出确认。
     * 入参说明：无
     * 返回值说明：无
     */
    handleStartFaceRecognition() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        if (State.faceRecognition.paused) {
            this.runStartFaceRecognition();
            return;
        }
        UIComponents.showConfirmModal({
            title: I18nManager.t('album.face_start_confirm_title'),
            message: I18nManager.t('album.face_start_confirm_msg'),
            confirmText: I18nManager.t('album.face_start'),
            onConfirm: () => this.runStartFaceRecognition()
        });
    },

    /**
     * 用途说明：调用后端将当前仓库未识别图片去重入队并启动或恢复识别。
     * 入参说明：无
     * 返回值说明：无
     */
    runStartFaceRecognition() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIController.setFaceBusy(true);
        API.startFaceRecognition((data) => {
            UIController.setFaceBusy(false);
            UIController.renderFaceStatus(data);
            Toast.show(I18nManager.t('album.face_start_success'));
            this.refreshFaceStatus();
        }, (msg) => {
            UIController.setFaceBusy(false);
            Toast.show(msg || I18nManager.t('album.face_start_failed'));
            this.refreshFaceStatus();
        });
    },

    /**
     * 用途说明：请求暂停当前仓库的人脸识别任务。
     * 入参说明：无
     * 返回值说明：无
     */
    handlePauseFaceRecognition() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIController.setFaceBusy(true);
        API.pauseFaceRecognition((data) => {
            UIController.setFaceBusy(false);
            UIController.renderFaceStatus(data);
            Toast.show(I18nManager.t('album.face_pause_success'));
            this.refreshFaceStatus();
        }, (msg) => {
            UIController.setFaceBusy(false);
            Toast.show(msg || I18nManager.t('album.face_pause_failed'));
            this.refreshFaceStatus();
        });
    },

    /**
     * 用途说明：停止识别前二次确认，明确提示会清空整个待识别队列。
     * 入参说明：无
     * 返回值说明：无
     */
    handleStopFaceRecognition() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIComponents.showConfirmModal({
            title: I18nManager.t('album.face_stop_confirm_title'),
            message: I18nManager.t('album.face_stop_confirm_msg'),
            confirmText: I18nManager.t('album.face_stop'),
            onConfirm: () => this.runStopFaceRecognition()
        });
    },

    /**
     * 用途说明：调用后端停止识别并清空当前仓库整个待识别队列。
     * 入参说明：无
     * 返回值说明：无
     */
    runStopFaceRecognition() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIController.setFaceBusy(true);
        API.stopFaceRecognition((data) => {
            UIController.setFaceBusy(false);
            UIController.renderFaceStatus(data);
            Toast.show(I18nManager.t('album.face_stop_success'));
            this.refreshFaceStatus();
        }, (msg) => {
            UIController.setFaceBusy(false);
            Toast.show(msg || I18nManager.t('album.face_stop_failed'));
            this.refreshFaceStatus();
        });
    },

    /**
     * 用途说明：弹出确认框，明确提示清除会先停止识别任务。
     * 入参说明：无
     * 返回值说明：无
     */
    confirmClearFaceData() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIComponents.showConfirmModal({
            title: I18nManager.t('album.face_clear_confirm_title'),
            message: I18nManager.t('album.face_clear_confirm_msg'),
            confirmText: I18nManager.t('album.face_clear'),
            onConfirm: () => this.handleClearFaceData()
        });
    },

    /**
     * 用途说明：调用后端停止识别并清除当前仓库的人脸特征与处理状态。
     * 入参说明：无
     * 返回值说明：无
     */
    handleClearFaceData() {
        if (!State.faceRecognition.canManage || State.faceRecognition.busy) return;
        UIController.setFaceBusy(true);
        API.clearFaceRecognitionData((data) => {
            UIController.setFaceBusy(false);
            UIController.renderFaceStatus(data);
            Toast.show(I18nManager.t('album.face_clear_success'));
            this.refreshFaceStatus();
        }, (msg) => {
            UIController.setFaceBusy(false);
            Toast.show(msg || I18nManager.t('album.face_clear_failed'));
            this.refreshFaceStatus();
        });
    },

    /**
     * 用途说明：获取人脸任务状态并更新界面，任务运行期间自动轮询，结束后提示结果。
     * 入参说明：无
     * 返回值说明：无
     */
    refreshFaceStatus() {
        if (State.faceRecognition.timer) {
            clearTimeout(State.faceRecognition.timer);
            State.faceRecognition.timer = null;
        }
        if (!State.faceRecognition.canManage) return;

        const previousStatus = State.faceRecognition.status;
        API.getFaceStatus((data) => {
            UIController.renderFaceStatus(data);
            if (data.running) {
                State.faceRecognition.timer = setTimeout(() => this.refreshFaceStatus(), 1000);
            } else if (previousStatus === ProgressStatus.PROCESSING) {
                if (data.status === ProgressStatus.COMPLETED || data.status === ProgressStatus.STOPPED) {
                    Toast.show(data.message || I18nManager.t('common.success'));
                } else if (data.status === ProgressStatus.ERROR) {
                    Toast.show(I18nManager.t('common.error') + ': ' + (data.message || ''));
                }
            }
        }, (msg) => {
            console.error(I18nManager.t('album.face_status_load_failed'), msg);
        });
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