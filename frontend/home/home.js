/**
 * 用途说明：主页逻辑处理，负责展示系统概览信息、仓库详情统计及功能导航。
 */

// --- 状态管理 ---
const HomeState = {
    titleClickCount: 0, // 用于记录标题点击次数，开启隐藏入口
    repos: [], // 当前用户可见的仓库列表缓存
    currentRepoId: 1, // 当前选中的仓库 ID
    currentRepoPermission: '', // 当前仓库权限：admin/member
    isAdmin: false, // 当前用户是否系统管理员
    appVersion: '' // 已获取的应用版本号，语言切换时用于重新渲染版本文案
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化页面 UI，缓存关键 DOM 元素并初始化顶部栏。
     * @returns {void} - 返回值说明：无
     */
    init() {
        // 初始化多语言
        I18nManager.init();
        I18nManager.render();

        // 使用通用的 HeaderToolbar 初始化顶部栏
        HeaderToolbar.init({
            title: I18nManager.t('home.title'),
            backCallback: null, // 首页不需要返回按钮
            menuCallback: null,  // 首页暂时不需要右侧菜单
            showBack: false
        });

        // 在工具栏生成后挂载外观按钮，确保仓库下拉框与按钮都位于右上区域
        const headerRight = document.querySelector('.header-right');
        if (headerRight && !document.getElementById('home-appearance-actions')) {
            const appearanceActions = document.createElement('div');
            appearanceActions.id = 'home-appearance-actions';
            appearanceActions.className = 'appearance-actions home-appearance-actions';
            headerRight.appendChild(appearanceActions);
            AppearanceManager.mount('home-appearance-actions');
        }

        // 缓存统计展示相关的 DOM 元素
        this.elements = {
            totalCount: document.getElementById('repo-total-count'),
            totalSize: document.getElementById('repo-total-size'),
            updateTime: document.getElementById('repo-update-time'),
            btnCalc: document.getElementById('btn-calc-repo-stats'),
            headerTitle: document.querySelector('.header-title'), // 适配 default_header_toolbar 的类名
            testPageMenu: document.getElementById('menu-test-page')
        };

        // 让标题支持点击事件，用于触发隐藏入口
        if (this.elements.headerTitle) {
            this.elements.headerTitle.style.pointerEvents = 'auto';
            this.elements.headerTitle.style.cursor = 'default';
        }
    },

    /**
     * @description 用途说明：更新统计 UI 数据。
     * @param {Object} data - 入参说明：包含 total_count, total_size, update_time 的对象。
     * @returns {void} - 返回值说明：无
     */
    updateStatsUI(data) {
        if (!data) return;
        if (this.elements.totalCount) this.elements.totalCount.textContent = data.total_count ?? 0;
        if (this.elements.totalSize) {
            // 调用公用工具类格式化文件大小
            this.elements.totalSize.textContent = CommonUtils.formatFileSize(data.total_size ?? 0);
        }
        if (this.elements.updateTime) {
            if (!data.update_time) {
                this.elements.updateTime.textContent = '--';
            } else {
                // 使用通用工具类转换日期部分为友好格式，并保留时间部分
                const friendlyDate = CommonUtils.formatFriendlyDate(data.update_time);
                const date = new Date(data.update_time);
                const timeStr = String(date.getHours()).padStart(2, '0') + ':' + 
                               String(date.getMinutes()).padStart(2, '0') + ':' + 
                               String(date.getSeconds()).padStart(2, '0');
                this.elements.updateTime.textContent = `${friendlyDate} ${timeStr}`;
            }
        }
    },

    /**
     * @description 用途说明：切换展示状态为“计算中”，激活按钮旋转动画。
     * @returns {void} - 返回值说明：无
     */
    setLoadingState() {
        if (this.elements.btnCalc) this.elements.btnCalc.classList.add('rotating');
    },

    /**
     * @description 用途说明：清除“计算中”加载状态。
     * @returns {void} - 返回值说明：无
     */
    clearLoadingState() {
        if (this.elements.btnCalc) this.elements.btnCalc.classList.remove('rotating');
    },

    /**
     * @description 用途说明：显示隐藏的测试入口。
     * @returns {void} - 返回值说明：无
     */
    showTestMenu() {
        if (this.elements.testPageMenu) {
            this.elements.testPageMenu.classList.remove('hidden');
            Toast.show('Debug mode enabled~');
        }
    },

    /**
     * @description 用途说明：在顶部工具栏右侧构建仓库切换下拉框，系统管理员额外显示“新增仓库”。
     * @param {Array} repos - 入参说明：当前用户可见的仓库列表 [{id, name, permission}]。
     * @param {number} currentId - 入参说明：当前选中的仓库 ID。
     * @param {boolean} canCreate - 入参说明：当前用户是否系统管理员。
     * @returns {void} - 返回值说明：无
     */
    buildRepoSelector(repos, currentId, canCreate) {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight) return;

        const old = document.getElementById('repo-selector-container');
        if (old) old.remove();

        const container = document.createElement('div');
        container.id = 'repo-selector-container';
        container.className = 'repo-selector-container';

        const select = document.createElement('select');
        select.id = 'repo-selector';
        select.className = 'repo-selector';
        select.title = I18nManager.t('repo.selector_title');

        repos.forEach(repo => {
            const opt = document.createElement('option');
            opt.value = String(repo.id);
            opt.textContent = repo.name;
            select.appendChild(opt);
        });

        if (canCreate) {
            const addOpt = document.createElement('option');
            addOpt.value = '__add__';
            addOpt.textContent = I18nManager.t('repo.add_new');
            select.appendChild(addOpt);
        }

        select.disabled = repos.length === 0 && !canCreate;
        select.value = repos.length ? String(currentId) : (canCreate ? '__add__' : '');
        container.appendChild(select);

        const selectorIcon = document.createElement('span');
        selectorIcon.className = 'repo-selector-icon theme-icon icon-chevron-down';
        selectorIcon.setAttribute('aria-hidden', 'true');
        container.appendChild(selectorIcon);

        headerRight.insertBefore(container, headerRight.firstChild);
        this.elements.repoSelector = select;
    },

    /**
     * @description 用途说明：刷新首页动态生成的标题、仓库下拉框提示与版本文案。
     * @returns {void} - 返回值说明：无。
     */
    refreshDynamicTexts() {
        if (this.elements.headerTitle) this.elements.headerTitle.textContent = I18nManager.t('home.title');
        const select = document.getElementById('repo-selector');
        if (select) {
            select.title = I18nManager.t('repo.selector_title');
            const addOption = Array.from(select.options).find(option => option.value === '__add__');
            if (addOption) addOption.textContent = I18nManager.t('repo.add_new');
        }
        this.renderAppVersion();
    },

    /**
     * @description 用途说明：按当前语言渲染已获取的应用版本号。
     * @returns {void} - 返回值说明：无。
     */
    renderAppVersion() {
        const versionDisplay = document.getElementById('app-version-display');
        if (versionDisplay && HomeState.appVersion) {
            versionDisplay.textContent = `${I18nManager.t('home.version')}: ${HomeState.appVersion}`;
        }
    },

    /**
     * @description 用途说明：按当前仓库权限调整首页菜单，仓库成员仅保留相册浏览与退出登录。
     * @returns {void} - 返回值说明：无
     */
    applyMenuPermissions() {
        const isMember = HomeState.currentRepoPermission === 'member';
        const hasRepo = HomeState.currentRepoId > 0;
        const toggle = (id, hidden) => {
            const element = document.getElementById(id);
            if (element) element.classList.toggle('hidden', hidden);
        };
        ['group-file-entry-title', 'group-file-entry-grid', 'group-organize-title', 'group-organize-grid',
            'group-file-manage-title', 'group-file-manage-grid'].forEach(id => toggle(id, isMember));
        toggle('menu-album-setting', isMember);
        toggle('menu-album-browse', !hasRepo);
        toggle('group-album-title', !hasRepo);
        toggle('menu-setting', isMember);
        toggle('menu-logs', isMember);
        toggle('menu-test-page', true);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * @description 用途说明：初始化应用，绑定事件并加载初始数据。
     * @returns {void} - 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        document.addEventListener('appearance:languagechange', () => UIController.refreshDynamicTexts());
        this.initRepoSelector();
        this.fetchAndDisplayAppVersion();
    },

    /**
     * @description 用途说明：加载仓库列表并初始化右上角仓库切换下拉框。
     * @returns {void} - 返回值说明：无
     */
    initRepoSelector() {
        HomeRequest.getCurrentUser(
            (userInfo) => {
                HomeState.isAdmin = Boolean(userInfo.is_admin);
                RepositoryRequest.list(
                    (repos) => {
                        HomeState.repos = repos || [];
                        let currentId = RepoContext.get();
                        // 当前仓库无权限或已删除时回退到首个可见仓库；无可见仓库时不回退默认仓库
                        if (!HomeState.repos.some(r => r.id === currentId)) {
                            currentId = HomeState.repos.length ? HomeState.repos[0].id : 0;
                            if (currentId > 0) RepoContext.set(currentId);
                            else RepoContext.clear();
                        }
                        HomeState.currentRepoId = currentId;
                        const currentRepo = HomeState.repos.find(r => r.id === currentId);
                        HomeState.currentRepoPermission = currentRepo ? currentRepo.permission : '';
                        UIController.buildRepoSelector(HomeState.repos, currentId, HomeState.isAdmin);
                        this.bindRepoSelector();
                        UIController.applyMenuPermissions();
                        if (currentId > 0 && HomeState.currentRepoPermission !== 'member') this.loadRepoStats();
                    },
                    (msg) => console.error('Failed to load repositories:', msg)
                );
            },
            (msg) => console.error('Failed to load current user:', msg)
        );
    },

    /**
     * @description 用途说明：绑定仓库下拉框的切换事件。
     * @returns {void} - 返回值说明：无
     */
    bindRepoSelector() {
        const select = UIController.elements.repoSelector;
        if (!select) return;
        select.onchange = () => this.onRepoSelectorChange(select.value);
    },

    /**
     * @description 用途说明：处理仓库下拉框选择变更，切换仓库或触发新增仓库流程。
     * @param {string} value - 入参说明：选中项的值（仓库 ID 字符串或 '__add__'）。
     * @returns {void} - 返回值说明：无
     */
    onRepoSelectorChange(value) {
        if (value === '__add__') {
            this.createRepoFlow();
            return;
        }
        const id = parseInt(value, 10);
        RepoContext.set(id);
        HomeState.currentRepoId = id;
        const repo = HomeState.repos.find(r => r.id === id);
        HomeState.currentRepoPermission = repo ? repo.permission : '';
        Toast.show(I18nManager.t('repo.switch_success', { name: repo ? repo.name : '' }));
        UIController.applyMenuPermissions();
        if (HomeState.currentRepoPermission !== 'member') this.loadRepoStats();
    },

    /**
     * @description 用途说明：新增仓库流程，弹窗要求输入仓库名，创建成功后切换到新仓库。
     * @returns {void} - 返回值说明：无
     */
    createRepoFlow() {
        if (!HomeState.isAdmin) return;
        const select = UIController.elements.repoSelector;
        const resetSelector = () => {
            if (select) select.value = String(HomeState.currentRepoId);
        };

        UIComponents.showInputModal({
            title: I18nManager.t('repo.add_title'),
            placeholder: I18nManager.t('repo.add_placeholder'),
            isSmall: true,
            onConfirm: (name) => {
                if (!name) {
                    Toast.show(I18nManager.t('repo.name_required'));
                    resetSelector();
                    return;
                }
                RepositoryRequest.create(name,
                    (data) => {
                        Toast.show(I18nManager.t('repo.add_success'));
                        RepoContext.set(data.id);
                        HomeState.currentRepoId = data.id;
                        this.initRepoSelector();
                        this.loadRepoStats();
                    },
                    (msg) => {
                        Toast.show(msg || I18nManager.t('repo.add_failed'));
                        resetSelector();
                    }
                );
            }
        });

        // 取消新增时恢复下拉框选中项
        const cancelBtn = document.getElementById('common-modal-input-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', resetSelector);
        }
    },

    /**
     * @description 用途说明：页面初始化时加载并展示仓库统计数据。
     * @returns {void} - 返回值说明：无
     */
    loadRepoStats() {
        if (HomeState.currentRepoId <= 0 || HomeState.currentRepoPermission === 'member') return;
        HomeRequest.getRepoDetail(
            (data) => {
                UIController.updateStatsUI(data);
            },
            (msg) => {
                console.error(msg);
            }
        );
    },

    /**
     * @description 用途说明：处理“计算”按钮点击事件。
     * @returns {void} - 返回值说明：无
     */
    handleCalculateStats() {
        if (HomeState.currentRepoPermission === 'member') return;
        // 1. 切换 UI 至加载状态
        UIController.setLoadingState();

        // 2. 发起计算请求（已配置不显示全局蒙版）
        HomeRequest.calculateRepoDetail(
            (data) => {
                UIController.clearLoadingState();
                Toast.show(I18nManager.t('home.stats_updated'));
                UIController.updateStatsUI(data);
            },
            (msg) => {
                UIController.clearLoadingState();
                Toast.show(msg || I18nManager.t('common.error'));
                this.loadRepoStats(); // 失败时尝试恢复展示旧数据
            }
        );
    },

    /**
     * @description 用途说明：获取并显示应用版本号。
     * @returns {void} - 返回值说明：无
     */
    fetchAndDisplayAppVersion() {
        HomeRequest.getAppVersion(
            (data) => {
                if (data && data.version) {
                    HomeState.appVersion = data.version;
                    UIController.renderAppVersion();
                }
            },
            (msg) => {
                console.error('Failed to fetch app version:', msg);
            }
        );
    },

    /**
     * @description 用途说明：注销登录逻辑，清除本地状态并跳转。
     * @returns {void} - 返回值说明：无
     */
    logout() {
        UIComponents.showConfirmModal({
            title: I18nManager.t('common.logout_confirm_title'),
            message: I18nManager.t('common.logout_confirm_msg'),
            confirmText: I18nManager.t('common.confirm'),
            onConfirm: () => {
                HomeRequest.logout(
                    () => {
                        Request.eraseCookie('token');
                        window.location.href = '../login/login.html';
                    },
                    (msg) => {
                        console.error('Logout failed:', msg);
                        // 即使后端失败，前端也尝试清理并跳转
                        Request.eraseCookie('token');
                        window.location.href = '../login/login.html';
                    }
                );
            }
        });
    },

    /**
     * @description 用途说明：绑定页面交互事件，包括功能卡片导航和统计刷新。
     * @returns {void} - 返回值说明：无
     */
    bindEvents() {
        // 绑定功能卡片点击
        const cards = document.querySelectorAll('.menu-item');
        cards.forEach(card => {
            card.onclick = () => {
                const map = {
                    'menu-file-repository': '../file_repository/file_repository.html',
                    'menu-duplicate-check': '../file_repository/duplicate_check/duplicate_check.html',
                    'menu-pending-entry': '../file_name_repository/pending_entry_file/pending_entry_file.html',
                    'menu-ignore-file': '../file_name_repository/already_entered_file/already_entered_file.html',
                    'menu-recycle-bin': '../file_repository/recycle_bin/recycle_bin.html',
                    'menu-album-browse': '../album/album_browse.html',
                    'menu-album-setting': '../album/album_setting.html',
                    'menu-organize-setting': '../organize/organize_setting.html',
                    'menu-organize-start': '../organize/organize_task.html',
                    'menu-organize-records': '../organize/organize_records.html',
                    'menu-setting': '../setting/setting.html',
                    'menu-logs': '../system/logs/logs.html',
                    'menu-test-page': '../test_page/test_progress_button.html',
                    'menu-logout': 'LOGOUT' // 特殊标识处理退出
                };
                const target = map[card.id];
                if (target === 'LOGOUT') {
                    this.logout();
                } else if (target) {
                    window.location.href = target;
                }
            };
        });

        // 绑定统计刷新按钮事件
        if (UIController.elements.btnCalc) {
            UIController.elements.btnCalc.onclick = (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                this.handleCalculateStats();
            };
        }

        // 绑定标题点击计数事件
        if (UIController.elements.headerTitle) {
            UIController.elements.headerTitle.onclick = () => {
                HomeState.titleClickCount++;
                if (HomeState.titleClickCount >= 3) {
                    UIController.showTestMenu();
                }
            };
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
