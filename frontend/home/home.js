/**
 * 用途说明：主页逻辑处理，负责展示系统概览信息、仓库详情统计及功能导航。
 */

// --- 状态管理 ---
const HomeState = {
    repos: [], // 当前用户可见的仓库列表缓存
    currentRepoId: 1, // 当前选中的仓库 ID
    currentRepoPermission: '', // 当前仓库权限：admin/member
    isAdmin: false, // 当前用户是否系统管理员
    canViewChangelog: false, // 是否为系统管理员或任一仓库管理员
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
            title: '', // 首页标题位置改为仓库切换下拉框
            backCallback: null, // 首页不需要返回按钮
            menuCallback: null,  // 首页暂时不需要右侧菜单
            showBack: false
        });

        // 首页左右操作区等宽，确保中间标题始终居中
        const headerBar = document.querySelector('.header-bar');
        if (headerBar) headerBar.classList.add('home-header');

        // 顶部栏生成后把主题与语言按钮挂载到最左侧
        const headerLeft = document.querySelector('.header-left');
        if (headerLeft && !document.getElementById('home-appearance-actions')) {
            const appearanceActions = document.createElement('div');
            appearanceActions.id = 'home-appearance-actions';
            appearanceActions.className = 'appearance-actions home-appearance-actions';
            headerLeft.appendChild(appearanceActions);
            AppearanceManager.mount('home-appearance-actions');
        }

        // 顶部栏生成后挂载统一当前任务入口
        CurrentTasksApp.start();

        // 缓存统计展示相关的 DOM 元素
        this.elements = {
            totalCount: document.getElementById('repo-total-count'),
            totalSize: document.getElementById('repo-total-size'),
            updateTime: document.getElementById('repo-update-time'),
            btnCalc: document.getElementById('btn-calc-repo-stats')
        };
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
     * @description 用途说明：在首页标题位置构建无边框仓库切换下拉框，系统管理员额外显示“新增仓库”。
     * @param {Array} repos - 入参说明：当前用户可见的仓库列表 [{id, name, permission}]。
     * @param {number} currentId - 入参说明：当前选中的仓库 ID。
     * @param {boolean} canCreate - 入参说明：当前用户是否系统管理员。
     * @returns {void} - 返回值说明：无
     */
    buildRepoSelector(repos, currentId, canCreate) {
        const titleContainer = document.querySelector('.home-header .header-title');
        if (!titleContainer) return;

        const old = document.getElementById('repo-selector-container');
        if (old) old.remove();

        const container = document.createElement('div');
        container.id = 'repo-selector-container';
        container.className = 'repo-selector-container home-repo-selector';

        const select = document.createElement('select');
        select.id = 'repo-selector';
        select.className = 'repo-selector home-repo-selector-control';
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

        // 用仓库切换控件替代首页标题，右侧只保留当前任务按钮
        titleContainer.replaceChildren(container);
        this.elements.repoSelector = select;
    },

    /**
     * @description 用途说明：刷新首页动态生成的仓库下拉框提示与版本文案。
     * @returns {void} - 返回值说明：无。
     */
    refreshDynamicTexts() {
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
        // 更新日志按全局管理角色显示，即使当前切换到成员仓库也仍可查看。
        toggle('menu-changelog', !HomeState.canViewChangelog);
        toggle('menu-test-page', true);
    }
};

// --- 更新日志弹窗模块 ---
const HomeChangelog = {
    VISIBLE_HIGHLIGHT_COUNT: 5,
    expandedVersions: new Set(),
    mode: 'unread',
    data: null,
    modal: null,
    content: null,
    closeIcon: null,
    closeButton: null,
    previousFocus: null,

    /**
     * @description 用途说明：缓存更新日志弹窗元素并绑定关闭、折叠和键盘交互。
     * @returns {void} - 返回值说明：无。
     */
    init() {
        this.modal = document.getElementById('changelog-modal');
        this.content = document.getElementById('changelog-content');
        this.closeIcon = document.getElementById('changelog-close-icon');
        this.closeButton = document.getElementById('changelog-close-button');
        if (!this.modal || !this.content) return;

        this.modal.addEventListener('click', (event) => {
            if (event.target === this.modal) this.close();
        });
        this.content.addEventListener('click', (event) => this.handleContentClick(event));
        if (this.closeIcon) this.closeIcon.addEventListener('click', () => this.close());
        if (this.closeButton) this.closeButton.addEventListener('click', () => this.close());
        document.addEventListener('keydown', (event) => this.handleKeydown(event));
    },

    /**
     * @description 用途说明：权限确定后检查未读版本，仅在需要时自动弹出。
     * @returns {void} - 返回值说明：无。
     */
    checkAuto() {
        if (!HomeState.canViewChangelog) return;
        HomeRequest.getChangelog(
            'unread',
            (data) => {
                if (data && data.auto_show) this.open('unread', data);
            },
            () => {} // 自动检查失败时保持安静，用户仍可通过菜单手动打开。
        );
    },

    /**
     * @description 用途说明：从菜单手动打开弹窗并展示全部版本日志。
     * @returns {void} - 返回值说明：无。
     */
    openManual() {
        if (!HomeState.canViewChangelog) return;
        HomeRequest.getChangelog(
            'all',
            (data) => this.open('all', data),
            () => Toast.show(I18nManager.t('home.changelog_load_failed'))
        );
    },

    /**
     * @description 用途说明：语言同步到后端后重新加载已打开弹窗的日志内容。
     * @returns {void} - 返回值说明：无。
     */
    refresh() {
        if (!this.isOpen()) return;
        const mode = this.mode;
        HomeRequest.getChangelog(
            mode,
            (data) => {
                if (!this.isOpen() || this.mode !== mode) return;
                this.data = data;
                this.render();
            },
            () => Toast.show(I18nManager.t('home.changelog_load_failed'))
        );
    },

    /**
     * @description 用途说明：判断更新日志弹窗当前是否打开。
     * @returns {boolean} - 返回值说明：打开返回 true，否则返回 false。
     */
    isOpen() {
        return Boolean(this.modal && !this.modal.classList.contains('hidden'));
    },

    /**
     * @description 用途说明：显示弹窗、渲染数据并将焦点移入弹窗。
     * @param {string} mode - 入参说明：unread 为自动未读模式，all 为手动全部模式。
     * @param {Object} data - 入参说明：后端返回的更新日志数据。
     * @returns {void} - 返回值说明：无。
     */
    open(mode, data) {
        if (!this.modal || !data) return;
        this.mode = mode;
        this.data = data;
        this.expandedVersions.clear();
        this.previousFocus = document.activeElement;
        this.render();
        this.modal.classList.remove('hidden');
        this.modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('changelog-open');
        if (this.closeIcon) {
            this.closeIcon.setAttribute('aria-label', I18nManager.t('home.changelog_close'));
            this.closeIcon.focus();
        }
    },

    /**
     * @description 用途说明：关闭弹窗并异步保存当前版本已读状态。
     * @returns {void} - 返回值说明：无。
     */
    close() {
        if (!this.isOpen()) return;
        const version = this.data && this.data.current_version ? this.data.current_version : '';
        this.modal.classList.add('hidden');
        this.modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('changelog-open');
        if (this.previousFocus && typeof this.previousFocus.focus === 'function') {
            this.previousFocus.focus();
        }
        if (!version) return;
        HomeRequest.markChangelogRead(
            version,
            () => {},
            () => Toast.show(I18nManager.t('home.changelog_read_failed'))
        );
    },

    /**
     * @description 用途说明：创建带主题类名和纯文本内容的 DOM 元素，避免插入日志 HTML。
     * @param {string} tagName - 入参说明：HTML 标签名。
     * @param {string} className - 入参说明：CSS 类名。
     * @param {string} text - 入参说明：可选文本内容。
     * @returns {HTMLElement} - 返回值说明：新创建的元素。
     */
    createElement(tagName, className = '', text = '') {
        const element = document.createElement(tagName);
        if (className) element.className = className;
        if (text) element.textContent = text;
        return element;
    },

    /**
     * @description 用途说明：渲染空状态或全部版本卡片。
     * @returns {void} - 返回值说明：无。
     */
    render() {
        if (!this.content || !this.data) return;
        this.content.replaceChildren();
        const entries = Array.isArray(this.data.entries) ? this.data.entries : [];
        if (!entries.length) {
            this.content.appendChild(this.createElement('div', 'changelog-empty', I18nManager.t('home.changelog_empty')));
            return;
        }
        entries.forEach(entry => {
            const section = this.createElement('section', 'changelog-version');
            section.dataset.version = entry.version;
            this.renderVersion(section, entry, this.expandedVersions.has(entry.version));
            this.content.appendChild(section);
        });
    },

    /**
     * @description 用途说明：渲染单个版本，默认只展示最重要的五条更新。
     * @param {HTMLElement} section - 入参说明：版本卡片容器。
     * @param {Object} entry - 入参说明：单个版本日志数据。
     * @param {boolean} expanded - 入参说明：是否已展开全部更新。
     * @returns {void} - 返回值说明：无。
     */
    renderVersion(section, entry, expanded) {
        section.replaceChildren();
        const header = this.createElement('div', 'changelog-version-header');
        const titleGroup = this.createElement('div', 'changelog-version-title-group');
        titleGroup.appendChild(this.createElement('h3', 'changelog-version-title', `v${entry.version}`));
        if (entry.version === this.data.current_version) {
            titleGroup.appendChild(this.createElement('span', 'changelog-latest', I18nManager.t('home.changelog_latest')));
        }
        header.appendChild(titleGroup);
        if (entry.date) header.appendChild(this.createElement('span', 'changelog-version-date', entry.date));
        section.appendChild(header);

        const highlights = Array.isArray(entry.highlights) ? entry.highlights : [];
        const visibleHighlights = expanded ? highlights : highlights.slice(0, this.VISIBLE_HIGHLIGHT_COUNT);
        const list = this.createElement('ol', 'changelog-highlight-list');
        visibleHighlights.forEach(highlight => {
            list.appendChild(this.createElement('li', 'changelog-highlight', highlight));
        });
        section.appendChild(list);

        if (highlights.length > this.VISIBLE_HIGHLIGHT_COUNT) {
            const remaining = highlights.length - this.VISIBLE_HIGHLIGHT_COUNT;
            const button = this.createElement(
                'button',
                'changelog-toggle',
                expanded
                    ? I18nManager.t('home.changelog_collapse')
                    : I18nManager.t('home.changelog_expand', { count: remaining })
            );
            button.type = 'button';
            button.dataset.changelogAction = 'toggle';
            button.dataset.version = entry.version;
            button.setAttribute('aria-expanded', String(expanded));
            section.appendChild(button);
        }

        if (entry.rebuild_index_notice) {
            const notice = this.createElement('div', 'changelog-rebuild-notice');
            notice.appendChild(this.createElement(
                'strong',
                'changelog-rebuild-title',
                I18nManager.t('home.changelog_rebuild_title')
            ));
            notice.appendChild(this.createElement('p', 'changelog-rebuild-text', entry.rebuild_index_notice));
            section.appendChild(notice);
        }
    },

    /**
     * @description 用途说明：处理版本更新列表的展开与收起点击。
     * @param {Event} event - 入参说明：内容区域冒泡的点击事件。
     * @returns {void} - 返回值说明：无。
     */
    handleContentClick(event) {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const button = target.closest('[data-changelog-action="toggle"]');
        if (!button || !this.data) return;
        const version = button.dataset.version;
        const entry = this.data.entries.find(item => item.version === version);
        const section = button.closest('.changelog-version');
        if (!entry || !section) return;
        const expanded = !this.expandedVersions.has(version);
        if (expanded) this.expandedVersions.add(version);
        else this.expandedVersions.delete(version);
        this.renderVersion(section, entry, expanded);
        const nextButton = section.querySelector('.changelog-toggle');
        if (nextButton) nextButton.focus();
    },

    /**
     * @description 用途说明：处理 Escape 关闭和 Tab 焦点循环，避免键盘操作跑到弹窗外。
     * @param {KeyboardEvent} event - 入参说明：文档键盘事件。
     * @returns {void} - 返回值说明：无。
     */
    handleKeydown(event) {
        if (!this.isOpen()) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            this.close();
            return;
        }
        if (event.key !== 'Tab') return;
        const focusable = Array.from(this.modal.querySelectorAll('button:not([disabled])'));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
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
        HomeChangelog.init();
        this.bindEvents();
        // 首页语言切换同时刷新动态文案，并同步后端配置以统一全站接口提示语言
        document.addEventListener('appearance:languagechange', () => {
            UIController.refreshDynamicTexts();
            HomeRequest.updateLanguage(
                I18nManager.currentLang,
                () => HomeChangelog.refresh(),
                () => Toast.show(I18nManager.t('common.language_sync_failed'))
            );
        });
        this.initRepoSelector();
        this.fetchAndDisplayAppVersion();
    },

    /**
     * @description 用途说明：加载仓库列表并初始化首页中央仓库切换下拉框。
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
                        HomeState.canViewChangelog = HomeState.isAdmin || HomeState.repos.some(repo => repo.permission === 'admin');
                        UIController.buildRepoSelector(HomeState.repos, currentId, HomeState.isAdmin);
                        this.bindRepoSelector();
                        UIController.applyMenuPermissions();
                        HomeChangelog.checkAuto();
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

        // 更新日志不跳转页面，点击后展示全部版本。
        const changelogMenu = document.getElementById('menu-changelog');
        if (changelogMenu) changelogMenu.onclick = () => HomeChangelog.openManual();

        // 绑定统计刷新按钮事件
        if (UIController.elements.btnCalc) {
            UIController.elements.btnCalc.onclick = (e) => {
                e.stopPropagation(); // 阻止事件冒泡
                this.handleCalculateStats();
            };
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
