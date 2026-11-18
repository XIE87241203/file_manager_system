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
        auto_refresh_time: "04:00",
        auto_duplicate_check_enabled: false
    },
    duplicateCheck: {
        image_threshold: 8,
        video_frame_similar_distance: 5,
        video_frame_similarity_rate: 0.7,
        video_interval_seconds: 30,
        video_max_duration_diff_ratio: 0.6,
        video_backwards: false,
        video_max_frames: 60
    },
    fileNameEntry: {
        file_name_link_prefix: ""
    },
    userData: {
        language: "en",
        login_max_attempts: 3,
        login_lockout_minutes: 5
    },
    // 缩略图同步任务状态
    thumbnailSync: {
        timer: null,
        widget: null,
        status: 'idle' // 记录同步任务的内部状态，初始为 idle
    },
    // 多仓库管理状态
    repos: [], // 仓库列表缓存
    currentRepoId: 1, // 当前编辑/激活的仓库 ID
    // 用户管理状态
    users: [], // 用户列表缓存
    isAdmin: false, // 当前登录用户是否管理员
    currentUsername: '', // 当前登录名
    editingUserId: null // 弹窗正在修改密码的用户 ID（null 表示新增用户）
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
            { btn: 'tab-account', content: 'content-account' },
            { btn: 'tab-user', content: 'content-user' }
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
                    // 切到用户管理分页时刷新用户列表
                    if (tab.btn === 'tab-user') App.loadUsers();
                };
            }
        });
    },

    /**
     * @description 用途说明：渲染用户列表表格（登录名、角色徽标、创建时间、操作按钮）
     * @returns {void} - 返回值说明：无
     */
    renderUserTable() {
        const tbody = document.getElementById('user-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';
        const users = State.users;
        if (!users.length) {
            tbody.innerHTML = UIComponents.getEmptyTableHtml(4);
            return;
        }
        users.forEach(user => {
            const tr = document.createElement('tr');

            const tdName = document.createElement('td');
            tdName.textContent = user.username;
            tr.appendChild(tdName);

            const tdRole = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = 'role-badge ' + (user.is_admin ? 'admin' : 'normal');
            badge.textContent = I18nManager.t(user.is_admin ? 'setting.user.role_admin' : 'setting.user.role_normal');
            tdRole.appendChild(badge);
            tr.appendChild(tdRole);

            const tdTime = document.createElement('td');
            tdTime.textContent = user.create_time || '';
            tr.appendChild(tdTime);

            const tdActions = document.createElement('td');
            const pwdBtn = document.createElement('button');
            pwdBtn.className = 'user-action-btn';
            pwdBtn.textContent = I18nManager.t('setting.user.edit_password');
            pwdBtn.onclick = (e) => { e.stopPropagation(); App.openUserModal(user.id); };
            tdActions.appendChild(pwdBtn);

            // 不能删除自己，故当前登录用户行不显示删除按钮
            if (user.username !== State.currentUsername) {
                const delBtn = document.createElement('button');
                delBtn.className = 'user-action-btn danger';
                delBtn.textContent = I18nManager.t('common.delete');
                delBtn.onclick = (e) => { e.stopPropagation(); App.handleDeleteUser(user); };
                tdActions.appendChild(delBtn);
            }
            tr.appendChild(tdActions);

            tbody.appendChild(tr);
        });
    },

    /**
     * @description 用途说明：显示用户弹窗。userId 为 null 时是新增用户（显示登录名输入），否则为修改密码（隐藏登录名）
     * @param {number|null} userId - 入参说明：目标用户 ID（null 表示新增）
     * @returns {void} - 返回值说明：无
     */
    showUserModal(userId) {
        const modal = document.getElementById('user-modal');
        const title = document.getElementById('user-modal-title');
        const usernameGroup = document.getElementById('user-modal-username-group');
        const usernameInput = document.getElementById('user-modal-username');
        document.getElementById('user-modal-password').value = '';
        document.getElementById('user-modal-confirm').value = '';
        if (userId === null) {
            title.textContent = I18nManager.t('setting.user.add_title');
            usernameGroup.classList.remove('hidden');
            usernameInput.value = '';
        } else {
            title.textContent = I18nManager.t('setting.user.edit_password_title');
            usernameGroup.classList.add('hidden');
            const user = State.users.find(u => u.id === userId);
            usernameInput.value = user ? user.username : '';
        }
        modal.classList.remove('hidden');
        (userId === null ? usernameInput : document.getElementById('user-modal-password')).focus();
    },

    /**
     * @description 用途说明：隐藏用户弹窗
     * @returns {void} - 返回值说明：无
     */
    hideUserModal() {
        const modal = document.getElementById('user-modal');
        if (modal) modal.classList.add('hidden');
    },

    /**
     * @description 用途说明：将配置数据填充到表单输入框中
     * @param {Object} data - 入参说明：后端返回的配置总览数据
     * @returns {void} - 返回值说明：无
     */
    fillSettingsForm(data) {
        // 用户数据（登录名与密码已移至用户管理，此处仅语言与锁定参数）
        State.userData = data.user_data || State.userData;
        const userData = State.userData;
        document.getElementById('language-select').value = userData.language || 'en';
        // 登录失败锁定参数（后端未返回时使用默认值）
        document.getElementById('login-max-attempts').value = userData.login_max_attempts ?? 3;
        document.getElementById('login-lockout-minutes').value = userData.login_lockout_minutes ?? 5;

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
        document.getElementById('video-max-frames').value = dc.video_max_frames ?? 60;
        document.getElementById('video-max-duration-diff-ratio').value = dc.video_max_duration_diff_ratio;
        document.getElementById('video-backwards').checked = dc.video_backwards || false;
    },

    /**
     * @description 用途说明：将指定仓库的独立配置填充到仓库配置表单。
     * @param {Object} fr - 入参说明：仓库配置对象 (FileRepositorySettings)。
     * @returns {void} - 返回值说明：无
     */
    fillRepoForm(fr) {
        State.fileRepository = fr || State.fileRepository;
        const repo = State.fileRepository;
        document.getElementById('scan-suffixes').value = (repo.scan_suffixes || ["*"]).join(', ');
        document.getElementById('thumbnail-size').value = repo.thumbnail_size || 256;
        document.getElementById('quick-view-thumbnail').checked = repo.quick_view_thumbnail || false;
        document.getElementById('ignore-filenames').value = (repo.ignore_filenames || []).join(', ');
        document.getElementById('ignore-filenames-case-insensitive').checked = repo.ignore_filenames_case_insensitive;
        document.getElementById('ignore-paths').value = (repo.ignore_paths || []).join(', ');
        document.getElementById('ignore-paths-case-insensitive').checked = repo.ignore_paths_case_insensitive;
        document.getElementById('search-replace-chars').value = (repo.search_replace_chars || []).join(', ');
        document.getElementById('auto-refresh-enabled').checked = repo.auto_refresh_enabled || false;
        document.getElementById('auto-refresh-time').value = repo.auto_refresh_time || "04:00";
        document.getElementById('auto-duplicate-check-enabled').checked = repo.auto_duplicate_check_enabled || false;
        this.renderRepositoryList();
    },

    /**
     * @description 用途说明：构建仓库配置页的仓库选择下拉框。
     * @param {Array} repos - 入参说明：仓库列表 [{id, name}]。
     * @param {number} currentId - 入参说明：当前选中的仓库 ID。
     * @returns {void} - 返回值说明：无
     */
    buildRepoSelector(repos, currentId) {
        const select = document.getElementById('repo-config-selector');
        if (!select) return;
        select.innerHTML = '';
        repos.forEach(repo => {
            const opt = document.createElement('option');
            opt.value = String(repo.id);
            opt.textContent = repo.name;
            select.appendChild(opt);
        });
        select.value = String(currentId);
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
            const empty = document.createElement('div');
            empty.className = 'empty-hint-text';
            empty.textContent = I18nManager.t('common.no_data');
            listContainer.appendChild(empty);
            return;
        }

        directories.forEach((path, index) => {
            const item = document.createElement('div');
            item.className = 'repo-item';

            const pathEl = document.createElement('div');
            pathEl.className = 'repo-path';
            pathEl.textContent = path;

            const actions = document.createElement('div');
            actions.className = 'repo-actions';
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-delete';
            deleteBtn.textContent = I18nManager.t('common.delete');
            deleteBtn.onclick = () => App.handleDeleteRepository(index);
            actions.appendChild(deleteBtn);

            item.appendChild(pathEl);
            item.appendChild(actions);
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
        this.initRepoSelector();
        this.bindEvents();
        // 加载当前用户信息，决定是否展示用户管理入口，并绑定用户管理交互
        this.loadCurrentUser();
        this.bindUserEvents();
        // 初始化时检查一次同步任务状态
        this.syncThumbnailProgress();
    },

    /**
     * @description 用途说明：加载当前登录用户信息，管理员则显示用户管理选项卡
     * @returns {void} - 返回值说明：无
     */
    loadCurrentUser() {
        SettingRequest.getCurrentUser(
            (data) => {
                State.currentUsername = data.username || '';
                State.isAdmin = !!data.is_admin;
                const tabBtn = document.getElementById('tab-user');
                if (tabBtn) tabBtn.classList.toggle('hidden', !State.isAdmin);
            },
            (msg) => {
                // 获取失败时保持用户管理入口隐藏，不影响其他设置功能
                console.error('loadCurrentUser failed:', msg);
            }
        );
    },

    /**
     * @description 用途说明：加载用户列表并渲染（仅管理员）
     * @returns {void} - 返回值说明：无
     */
    loadUsers() {
        if (!State.isAdmin) return;
        SettingRequest.getUserList(
            (users) => {
                State.users = users || [];
                UIController.renderUserTable();
            },
            (msg) => Toast.show(msg)
        );
    },

    /**
     * @description 用途说明：绑定用户管理分页的按钮与弹窗事件
     * @returns {void} - 返回值说明：无
     */
    bindUserEvents() {
        const addBtn = document.getElementById('add-user-btn');
        if (addBtn) addBtn.onclick = () => this.openUserModal(null);

        const confirmBtn = document.getElementById('user-modal-confirm-btn');
        if (confirmBtn) confirmBtn.onclick = () => this.submitUserModal();

        const cancelBtn = document.getElementById('user-modal-cancel-btn');
        if (cancelBtn) cancelBtn.onclick = () => UIController.hideUserModal();
    },

    /**
     * @description 用途说明：打开用户弹窗。userId 为 null 表示新增用户，否则为修改该用户密码
     * @param {number|null} userId - 入参说明：目标用户 ID（null 表示新增）
     * @returns {void} - 返回值说明：无
     */
    openUserModal(userId) {
        State.editingUserId = userId;
        UIController.showUserModal(userId);
    },

    /**
     * @description 用途说明：提交用户弹窗（新增用户或修改密码），校验后哈希密码并调用 API
     * @returns {void} - 返回值说明：无
     */
    submitUserModal() {
        const username = document.getElementById('user-modal-username').value.trim();
        const password = document.getElementById('user-modal-password').value;
        const confirm = document.getElementById('user-modal-confirm').value;

        // 新增用户时校验登录名
        if (State.editingUserId === null && !username) {
            Toast.show(I18nManager.t('setting.user.username_required'));
            return;
        }
        if (!password) {
            Toast.show(I18nManager.t('setting.user.password_required'));
            return;
        }
        if (password !== confirm) {
            Toast.show(I18nManager.t('setting.user.password_mismatch'));
            return;
        }

        // 与登录页一致：前端先做 SHA-256 哈希再传输
        const passwordHash = CryptoJS.SHA256(password).toString();
        const onSuccess = () => {
            UIController.hideUserModal();
            Toast.show(I18nManager.t('common.success'));
            this.loadUsers();
        };
        const onError = (msg) => Toast.show(msg);

        if (State.editingUserId === null) {
            SettingRequest.addUser(username, passwordHash, onSuccess, onError);
        } else {
            SettingRequest.updateUserPassword(State.editingUserId, passwordHash, onSuccess, onError);
        }
    },

    /**
     * @description 用途说明：删除用户（二次确认）
     * @param {Object} user - 入参说明：目标用户对象 {id, username}
     * @returns {void} - 返回值说明：无
     */
    handleDeleteUser(user) {
        UIComponents.showConfirmModal({
            title: I18nManager.t('common.hint'),
            message: I18nManager.t('setting.user.delete_confirm', { username: user.username }),
            confirmText: I18nManager.t('common.delete'),
            onConfirm: () => {
                SettingRequest.deleteUser(
                    user.id,
                    () => {
                        Toast.show(I18nManager.t('common.success'));
                        this.loadUsers();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * @description 用途说明：加载仓库列表并初始化仓库配置选择器，默认选中当前激活仓库。
     * @returns {void} - 返回值说明：无
     */
    initRepoSelector() {
        RepositoryRequest.list(
            (repos) => {
                State.repos = repos;
                let currentId = RepoContext.get();
                if (!repos.some(r => r.id === currentId)) {
                    currentId = repos.length ? repos[0].id : RepoContext.DEFAULT_REPO_ID;
                    RepoContext.set(currentId);
                }
                State.currentRepoId = currentId;
                UIController.buildRepoSelector(repos, currentId);
                this.loadRepoConfig(currentId);
            },
            (msg) => {
                Toast.show(I18nManager.t('repo.load_failed') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：加载指定仓库的独立配置并填充表单。
     * @param {number} repoId - 入参说明：仓库 ID。
     * @returns {void} - 返回值说明：无
     */
    loadRepoConfig(repoId) {
        RepositoryRequest.getConfig(repoId,
            (config) => {
                UIController.fillRepoForm(config);
            },
            (msg) => {
                Toast.show(I18nManager.t('common.error') + ': ' + msg);
            }
        );
    },

    /**
     * @description 用途说明：处理仓库配置选择器切换，更新激活仓库并加载其配置。
     * @param {number} repoId - 入参说明：选中的仓库 ID。
     * @returns {void} - 返回值说明：无
     */
    onRepoChange(repoId) {
        State.currentRepoId = repoId;
        RepoContext.set(repoId);
        this.loadRepoConfig(repoId);
    },

    /**
     * @description 用途说明：删除当前选中仓库，需二次确认；仅删除配置与索引，保留磁盘文件。
     * @returns {void} - 返回值说明：无
     */
    handleDeleteRepo() {
        if (State.repos.length <= 1) {
            Toast.show(I18nManager.t('repo.delete_last_blocked'));
            return;
        }
        const repo = State.repos.find(r => r.id === State.currentRepoId);
        const name = repo ? repo.name : '';
        UIComponents.showConfirmModal({
            title: I18nManager.t('repo.delete_title'),
            message: I18nManager.t('repo.delete_confirm', { name }),
            onConfirm: () => {
                // 二次确认
                UIComponents.showConfirmModal({
                    title: I18nManager.t('repo.delete_title'),
                    message: I18nManager.t('repo.delete_confirm_again'),
                    onConfirm: () => {
                        RepositoryRequest.delete(State.currentRepoId,
                            () => {
                                Toast.show(I18nManager.t('repo.delete_success'));
                                this.initRepoSelector();
                            },
                            (msg) => {
                                Toast.show(msg || I18nManager.t('repo.delete_failed'));
                            }
                        );
                    }
                });
            }
        });
    },

    /**
     * @description 用途说明：绑定页面基础交互事件
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        document.getElementById('add-repo-btn').onclick = () => this.handleAddRepository();
        document.getElementById('delete-repo-btn').onclick = () => this.handleDeleteRepo();
        const repoSelector = document.getElementById('repo-config-selector');
        if (repoSelector) {
            repoSelector.onchange = () => this.onRepoChange(parseInt(repoSelector.value, 10));
        }

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
        fr.auto_duplicate_check_enabled = document.getElementById('auto-duplicate-check-enabled').checked;

        if (fr.scan_suffixes.length === 0) {
            Toast.show(I18nManager.t('setting.repo.scan_suffixes_empty'));
            return;
        }

        // 2. 采集查重配置数据
        const maxFrames = parseInt(document.getElementById('video-max-frames').value);
        // 限张校验：必须为整数，且为 -1（不限）或正整数
        if (isNaN(maxFrames) || (maxFrames !== -1 && maxFrames < 1)) {
            Toast.show(I18nManager.t('setting.dup_check.video_max_frames_invalid'));
            return;
        }
        const dc = {
            image_threshold: parseInt(document.getElementById('image-threshold').value),
            video_frame_similar_distance: parseInt(document.getElementById('video-frame-similar-distance').value),
            video_frame_similarity_rate: parseFloat(document.getElementById('video-frame-similarity-rate').value),
            video_interval_seconds: parseInt(document.getElementById('video-interval-seconds').value),
            video_max_duration_diff_ratio: parseFloat(document.getElementById('video-max-duration-diff-ratio').value),
            video_backwards: document.getElementById('video-backwards').checked,
            video_max_frames: maxFrames
        };

        // 3. 采集文件录入配置数据
        const fe = {
            file_name_link_prefix: document.getElementById('file-name-link-prefix').value.trim()
        };

        // 4. 采集用户信息数据（登录名与密码改由用户管理维护，此处仅语言与锁定参数）
        const language = document.getElementById('language-select').value;
        // 登录失败锁定参数：必须为 >=1 的整数
        const loginMaxAttempts = parseInt(document.getElementById('login-max-attempts').value, 10);
        const loginLockoutMinutes = parseInt(document.getElementById('login-lockout-minutes').value, 10);

        if (!Number.isInteger(loginMaxAttempts) || loginMaxAttempts < 1 ||
            !Number.isInteger(loginLockoutMinutes) || loginLockoutMinutes < 1) {
            Toast.show(I18nManager.t('setting.account.security_params_invalid'));
            return;
        }

        const userData = {
            language,
            login_max_attempts: loginMaxAttempts,
            login_lockout_minutes: loginLockoutMinutes
        };

        const updateData = {
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
                            this.executeGlobalSave(updateData, isLanguageChanged);
                        },
                        (msg) => Toast.show(msg)
                    );
                }
            });
        } else {
            this.executeGlobalSave(updateData, isLanguageChanged);
        }
    },

    /**
     * @description 用途说明：发起 API 请求执行全站设置更新，并根据语言变更处理后续跳转逻辑
     * @param {Object} updateData - 入参说明：包含所有配置分类的更新对象
     * @param {boolean} isLanguageChanged - 入参说明：标记语言是否已更改，用于重定向至首页以应用新语言
     * @returns {void} - 返回值说明：无
     */
    executeGlobalSave(updateData, isLanguageChanged) {
        // 先保存当前仓库的独立配置，成功后再保存全局配置
        RepositoryRequest.updateConfig(State.currentRepoId, State.fileRepository,
            () => {
                SettingRequest.updateSettings(
                    updateData,
                    () => {
                        Toast.show(I18nManager.t('common.success'));

                        if (isLanguageChanged) {
                            // 语言变更后，重新刷新页面以应用新语言
                            I18nManager.init(updateData.user_data.language);
                            window.location.href = '../home/home.html';
                        } else {
                            this.loadSettings();
                            this.loadRepoConfig(State.currentRepoId);
                        }
                    },
                    (msg) => {
                        Toast.show(I18nManager.t('common.error') + ': ' + msg);
                    }
                );
            },
            (msg) => {
                Toast.show(I18nManager.t('repo.config_save_failed') + ': ' + msg);
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
