/**
 * 用途说明：主页逻辑处理，负责展示系统概览信息、仓库详情统计及功能导航。
 */

// --- 状态管理 ---
const HomeState = {
    titleClickCount: 0 // 用于记录标题点击次数，开启隐藏入口
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
        this.loadRepoStats();
        this.fetchAndDisplayAppVersion();
    },

    /**
     * @description 用途说明：页面初始化时加载并展示仓库统计数据。
     * @returns {void} - 返回值说明：无
     */
    loadRepoStats() {
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
                    const versionDisplay = document.getElementById('app-version-display');
                    if (versionDisplay) {
                        versionDisplay.textContent = `${I18nManager.t('home.version')}: ${data.version}`;
                    }
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
