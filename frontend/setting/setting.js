/**
 * @description 系统设置页面逻辑处理，负责加载和保存后端配置，处理选项卡切换和维护操作。
 */

// --- 状态管理 ---
const State = {
    fileRepository: {
        directories: [],
        scan_suffixes: ["*"],
        search_replace_chars: [],
        ignore_filenames: [],
        ignore_filenames_case_insensitive: true,
        ignore_paths: [],
        ignore_paths_case_insensitive: true,
        thumbnail_size: 256,
        quick_view_thumbnail: false,
        auto_refresh_enabled: false,
        auto_refresh_time: "04:00"
    },
    duplicateCheck: {
        image_threshold: 8,
        video_frame_similar_distance: 5,
        video_frame_similarity_rate: 0.7,
        video_interval_seconds: 30,
        video_max_duration_diff_ratio: 0.6,
        video_backwards: false
    },
    fileNameEntry: {
        file_name_link_prefix: ""
    },
    userData: {
        username: "admin",
        language: "en"
    },
    // 缩略图同步任务状态
    thumbnailSync: {
        timer: null,
        widget: null,
        status: 'idle' // 记录同步任务的内部状态，初始为 idle
    }
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化选项卡切换逻辑
     * @returns {void} - 返回值说明：无
     */
    initTabs() {
        const tabs = [
            { btn: 'tab-repo', content: 'content-repo' },
            { btn: 'tab-file-entry', content: 'content-file-entry' },
            { btn: 'tab-dup-check', content: 'content-dup-check' },
            { btn: 'tab-maintenance', content: 'content-maintenance' },
            { btn: 'tab-account', content: 'content-account' }
        ];

        tabs.forEach(tab => {
            const btnElement = document.getElementById(tab.btn);
            if (btnElement) {
                btnElement.onclick = () => {
                    tabs.forEach(t => {
                        const b = document.getElementById(t.btn);
                        const c = document.getElementById(t.content);
                        if (b) b.classList.remove('active');
                        if (c) c.classList.remove('active');
                    });
                    document.getElementById(tab.btn).classList.add('active');
                    document.getElementById(tab.content).classList.add('active');
                };
            }
        });
    },

    /**
     * @description 用途说明：将配置数据填充到表单输入框中
     * @param {Object} data - 入参说明：后端返回的配置总览数据
     * @returns {void} - 返回值说明：无
     */
    fillSettingsForm(data) {
        // 用户数据
        State.userData = data.user_data || State.userData;
        const userData = State.userData;
        document.getElementById('username').value = userData.username || '';
        document.getElementById('language-select').value = userData.language || 'en';
        document.getElementById('password').value = '';
        document.getElementById('confirm-password').value = '';

        // 根据后端配置初始化多语言并渲染
        I18nManager.init(userData.language);
        I18nManager.render();
        // 重新初始化 HeaderToolbar 以更新标题
        HeaderToolbar.init({
            title: I18nManager.t('setting.title'),
            showBack: true,
            menuIcon: '../../common/header_toolbar/icon/save_icon.svg',
            menuCallback: () => App.handleGlobalSave()
        });

        // 文件仓库配置同步到 State
        State.fileRepository = data.file_repository || State.fileRepository;
        const fr = State.fileRepository;
        document.getElementById('scan-suffixes').value = (fr.scan_suffixes || ["*"]).join(', ');
        document.getElementById('thumbnail-size').value = fr.thumbnail_size || 256;
        document.getElementById('quick-view-thumbnail').checked = fr.quick_view_thumbnail || false;
        document.getElementById('ignore-filenames').value = (fr.ignore_filenames || []).join(', ');
        document.getElementById('ignore-filenames-case-insensitive').checked = fr.ignore_filenames_case_insensitive;
        document.getElementById('ignore-paths').value = (fr.ignore_paths || []).join(', ');
        document.getElementById('ignore-paths-case-insensitive').checked = fr.ignore_paths_case_insensitive;
        document.getElementById('search-replace-chars').value = (fr.search_replace_chars || []).join(', ');

        // 自动刷新配置
        document.getElementById('auto-refresh-enabled').checked = fr.auto_refresh_enabled || false;
        document.getElementById('auto-refresh-time').value = fr.auto_refresh_time || "04:00";

        // 文件录入配置同步到 State
        State.fileNameEntry = data.file_name_entry || State.fileNameEntry;
        document.getElementById('file-name-link-prefix').value = State.fileNameEntry.file_name_link_prefix || '';

        // 查重配置同步到 State
        State.duplicateCheck = data.duplicate_check || State.duplicateCheck;
        const dc = State.duplicateCheck;
        document.getElementById('image-threshold').value = dc.image_threshold;
        document.getElementById('video-frame-similar-distance').value = dc.video_frame_similar_distance;
        document.getElementById('video-frame-similarity-rate').value = dc.video_frame_similarity_rate;
        document.getElementById('video-interval-seconds').value = dc.video_interval_seconds;
        document.getElementById('video-max-duration-diff-ratio').value = dc.video_max_duration_diff_ratio;
        document.getElementById('video-backwards').checked = dc.video_backwards || false;

        this.renderRepositoryList();
    },

    /**
     * @description 用途说明：渲染仓库路径列表
     * @returns {void} - 返回值说明：无
     */
    renderRepositoryList() {
        const listContainer = document.getElementById('repo-list');
        listContainer.innerHTML = '';
        const directories = State.fileRepository.directories;

        if (!directories || directories.length === 0) {
            listContainer.innerHTML = `<div class="empty-hint-text">${I18nManager.t('common.no_data')}</div>`;
            return;
        }

        directories.forEach((path, index) => {
            const item = document.createElement('div');
            item.className = 'repo-item';
            item.innerHTML = `
                <div class="repo-path">${path}</div>
                <div class="repo-actions">
                    <button class="btn-delete" data-index="${index}">${I18nManager.t('common.delete')}</button>
                </div>
            `;
            // 绑定删除按钮点击事件
            item.querySelector('.btn-delete').onclick = () => App.handleDeleteRepository(index);
            listContainer.appendChild(item);
        });
    },

    /**
     * @description 用途说明：初始化缩略图同步按钮组件
     * @returns {void} - 返回值说明：无
     */
    initThumbnailSyncButton() {
        const container = document.getElementById('sync-thumbnail-btn-container');
        if (!container) return;

        State.thumbnailSync.widget = ProgressButtonWidget.create({
            normalText: I18nManager.t('setting.maintenance.sync_thumb'),
            stopText: I18nManager.t('common.cancel'),
            defaultBgColor: '#007bff',
            onStart: () => App.handleStartThumbnailSync(),
            onStop: () => App.handleStopThumbnailSync()
        });

        container.appendChild(State.thumbnailSync.widget.getElement());
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * @description 用途说明：初始化应用，加载多语言、Header及设置数据
     * @returns {void} - 返回值说明：无
     */
    init() {
        // 先做基础渲染，API 加载后再精准渲染一次
        I18nManager.init();
        I18nManager.render();

        HeaderToolbar.init({
            title: I18nManager.t('setting.title'),
            showBack: true,
            menuIcon: '../../common/header_toolbar/icon/save_icon.svg',
            menuCallback: () => this.handleGlobalSave()
        });
        UIController.initTabs();
        UIController.initThumbnailSyncButton();
        this.loadSettings();
        this.bindEvents();
        // 初始化时检查一次同步任务状态
        this.syncThumbnailProgress();
    },

    /**
     * @description 用途说明：绑定页面基础交互事件
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        document.getElementById('add-repo-btn').onclick = () => this.handleAddRepository();

        // 危险操作按钮
        document.getElementById('clear-already-entered-btn').onclick = () => this.confirmClear('already_entered');
        document.getElementById('clear-pending-entry-btn').onclick = () => this.confirmClear('pending_entry');
        document.getElementById('clear-history-btn').onclick = () => this.confirmClear('history');
        document.getElementById('clear-video-btn').onclick = () => this.confirmClear('video');
    },

    /**
     * @description 用途说明：从后端异步加载系统配置并触发 UI 渲染
     * @returns {void} - 返回值说明：无
     */
    loadSettings() {
        SettingRequest.getSettings(
            (data) => {
                UIController.fillSettingsForm(data);
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：显示输入弹窗以添加新的仓库路径
     * @returns {void} - 返回值说明：无
     */
    handleAddRepository() {
        UIComponents.showInputModal({
            title: I18nManager.t('setting.repo.add_repo'),
            placeholder: I18nManager.t('setting.repo.repo_dir'),
            onConfirm: (value) => {
                const path = value.trim();
                if (!path) {
                    Toast.show(I18nManager.t('common.input_path'));
                    return;
                }
                if (State.fileRepository.directories.includes(path)) {
                    Toast.show(I18nManager.t('common.path_exists'));
                    return;
                }
                State.fileRepository.directories.push(path);
                UIController.renderRepositoryList();
            }
        });
    },

    /**
     * @description 用途说明：从本地 State 中移除指定索引的仓库路径并重新渲染列表
     * @param {number} index - 入参说明：待删除路径在数组中的索引
     * @returns {void} - 返回值说明：无
     */
    handleDeleteRepository(index) {
        State.fileRepository.directories.splice(index, 1);
        UIController.renderRepositoryList();
    },

    /**
     * @description 用途说明：收集表单数据并执行全站设置保存逻辑，包含关键参数变更检查
     * @returns {void} - 返回值说明：无
     */
    handleGlobalSave() {
        // 1. 采集文件仓库数据
        const fr = State.fileRepository;
        fr.scan_suffixes = document.getElementById('scan-suffixes').value.split(',').map(s => s.trim()).filter(s => s);
        fr.thumbnail_size = parseInt(document.getElementById('thumbnail-size').value);
        fr.quick_view_thumbnail = document.getElementById('quick-view-thumbnail').checked;
        fr.ignore_filenames = document.getElementById('ignore-filenames').value.split(',').map(s => s.trim()).filter(s => s);
        fr.ignore_filenames_case_insensitive = document.getElementById('ignore-filenames-case-insensitive').checked;
        fr.ignore_paths = document.getElementById('ignore-paths').value.split(',').map(s => s.trim()).filter(s => s);
        fr.ignore_paths_case_insensitive = document.getElementById('ignore-paths-case-insensitive').checked;
        fr.search_replace_chars = document.getElementById('search-replace-chars').value.split(',').map(s => s.trim()).filter(s => s);

        // 自动刷新字段采集
        fr.auto_refresh_enabled = document.getElementById('auto-refresh-enabled').checked;
        fr.auto_refresh_time = document.getElementById('auto-refresh-time').value;

        if (fr.scan_suffixes.length === 0) {
            Toast.show(I18nManager.t('setting.repo.scan_suffixes_empty'));
            return;
        }

        // 2. 采集查重配置数据
        const dc = {
            image_threshold: parseInt(document.getElementById('image-threshold').value),
            video_frame_similar_distance: parseInt(document.getElementById('video-frame-similar-distance').value),
            video_frame_similarity_rate: parseFloat(document.getElementById('video-frame-similarity-rate').value),
            video_interval_seconds: parseInt(document.getElementById('video-interval-seconds').value),
            video_max_duration_diff_ratio: parseFloat(document.getElementById('video-max-duration-diff-ratio').value),
            video_backwards: document.getElementById('video-backwards').checked
        };

        // 3. 采集文件录入配置数据
        const fe = {
            file_name_link_prefix: document.getElementById('file-name-link-prefix').value.trim()
        };

        // 4. 采集用户信息数据
        const username = document.getElementById('username').value.trim();
        const language = document.getElementById('language-select').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;

        if (!username) {
            Toast.show(I18nManager.t('login.username_placeholder'));
            return;
        }

        const userData = { username, language };
        let isPasswordChanged = false;
        if (password) {
            if (password !== confirmPassword) {
                Toast.show(I18nManager.t('setting.account.password_mismatch'));
                return;
            }
            userData.password = password;
            isPasswordChanged = true;
        }

        const updateData = {
            file_repository: fr,
            duplicate_check: dc,
            file_name_entry: fe,
            user_data: userData
        };

        // 5. 检查关键参数变更并执行保存
        const isIntervalChanged = dc.video_interval_seconds !== State.duplicateCheck.video_interval_seconds;
        const isBackwardsChanged = dc.video_backwards !== State.duplicateCheck.video_backwards;
        const isLanguageChanged = language !== State.userData.language;

        if (isIntervalChanged || isBackwardsChanged) {
            UIComponents.showConfirmModal({
                title: I18nManager.t('common.hint'),
                message: I18nManager.t('setting.dup_check.video_interval_hint'),
                onConfirm: () => {
                    SettingRequest.clearVideoFeatures(
                        () => {
                            this.executeGlobalSave(updateData, isPasswordChanged, isLanguageChanged);
                        },
                        (msg) => Toast.show(msg)
                    );
                }
            });
        } else {
            this.executeGlobalSave(updateData, isPasswordChanged, isLanguageChanged);
        }
    },

    /**
     * @description 用途说明：发起 API 请求执行全站设置更新，并根据变更项（如密码或语言）处理后续逻辑
     * @param {Object} updateData - 入参说明：包含所有配置分类的更新对象
     * @param {boolean} isPasswordChanged - 入参说明：标记密码是否已更改，用于重定向至登录页
     * @param {boolean} isLanguageChanged - 入参说明：标记语言是否已更改，用于重定向至首页以应用新语言
     * @returns {void} - 返回值说明：无
     */
    executeGlobalSave(updateData, isPasswordChanged, isLanguageChanged) {
        SettingRequest.updateSettings(
            updateData,
            () => {
                Toast.show(I18nManager.t('common.success'));

                if (isPasswordChanged) {
                    setTimeout(() => {
                        Request.eraseCookie('token');
                        window.location.href = '../login/login.html';
                    }, 1000);
                } else if (isLanguageChanged) {
                    // 语言变更后，重新刷新页面以应用新语言
                    I18nManager.init(updateData.user_data.language);
                    window.location.href = '../home/home.html';
                } else {
                    this.loadSettings();
                }
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：统一处理各种数据清理操作的二次确认及 API 触发逻辑
     * @param {string} type - 入参说明：清理类型标识，可选 'already_entered', 'pending_entry', 'history', 'video'
     * @returns {void} - 返回值说明：无
     */
    confirmClear(type) {
        const config = {
            already_entered: {
                title: I18nManager.t('setting.maintenance.clear_already_entered'),
                msg: I18nManager.t('setting.maintenance.clear_already_entered_desc'),
                api: (success, error) => SettingRequest.clearAlreadyEntered(success, error)
            },
            pending_entry: {
                title: I18nManager.t('setting.maintenance.clear_pending_entry'),
                msg: I18nManager.t('setting.maintenance.clear_pending_entry_desc'),
                api: (success, error) => SettingRequest.clearPendingEntry(success, error)
            },
            history: {
                title: I18nManager.t('setting.maintenance.clear_history'),
                msg: I18nManager.t('setting.maintenance.clear_history_desc'),
                api: (success, error) => SettingRequest.clearHistory(success, error)
            },
            video: {
                title: I18nManager.t('setting.maintenance.clear_video'),
                msg: I18nManager.t('setting.maintenance.clear_video_desc'),
                api: (success, error) => SettingRequest.clearVideoFeatures(success, error)
            }
        };
        const item = config[type];
        UIComponents.showConfirmModal({
            title: item.title,
            message: item.msg,
            onConfirm: () => {
                item.api(
                    (res) => {
                        Toast.show(res.message || I18nManager.t('common.success'));
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * @description 用途说明：触发后端执行缩略图同步清理任务
     * @returns {void} - 返回值说明：无
     */
    handleStartThumbnailSync() {
        SettingRequest.startThumbnailSync(
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
     * @description 用途说明：触发后端停止当前正在进行的缩略图同步任务
     * @returns {void} - 返回值说明：无
     */
    handleStopThumbnailSync() {
        SettingRequest.stopThumbnailSync(
            () => {
                Toast.show(I18nManager.t('common.success'));
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：异步获取缩略图同步进度，并根据状态更新 ProgressButtonWidget 的 UI 表现，支持自动轮询
     * @returns {void} - 返回值说明：无
     */
    syncThumbnailProgress() {
        if (State.thumbnailSync.timer) {
            clearTimeout(State.thumbnailSync.timer);
            State.thumbnailSync.timer = null;
        }

        SettingRequest.getThumbnailSyncProgress(
            (data) => {
                const { status, progress } = data;
                const widget = State.thumbnailSync.widget;

                if (status === ProgressStatus.PROCESSING) {
                    State.thumbnailSync.status = ProgressStatus.PROCESSING;
                    widget.setState('processing');
                    const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
                    // 设置进度时同时设置文案，格式为：正在处理：当前/总数
                    widget.setProgress(percent, `${I18nManager.t('common.loading')}：${progress.current}/${progress.total}`);

                    // 继续轮询
                    State.thumbnailSync.timer = setTimeout(() => this.syncThumbnailProgress(), 1000);
                } else {
                    // 用途说明：仅当之前的任务状态不是 idle 时（即刚从 processing 切换过来），才执行状态重置并弹出结果提示
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

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', () => App.init());
