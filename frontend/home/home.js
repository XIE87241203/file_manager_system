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
     * 用途说明：初始化页面 UI，缓存关键 DOM 元素并初始化顶部栏。
     */
    init() {
        // 初始化公用头部，主页不需要返回按钮，右侧添加退出登录按钮
        UIComponents.initHeader(
            '文件管理系统', 
            false, 
            null, 
            '退出登录', 
            () => App.logout(), 
            'btn-text-danger'
        );

        // 缓存统计展示相关的 DOM 元素
        this.elements = {
            totalCount: document.getElementById('repo-total-count'),
            totalSize: document.getElementById('repo-total-size'),
            updateTime: document.getElementById('repo-update-time'),
            btnCalc: document.getElementById('btn-calc-repo-stats'),
            headerTitle: document.querySelector('.top-bar-title'),
            testPageMenu: document.getElementById('menu-test-page')
        };

        // 特殊处理：让标题支持点击事件（覆盖 common.css 中的 pointer-events: none）
        if (this.elements.headerTitle) {
            this.elements.headerTitle.style.pointerEvents = 'auto';
            this.elements.headerTitle.style.cursor = 'default';
        }
    },

    /**
     * 用途说明：更新统计 UI 数据。
     * 入参说明：data (Object) - 包含 total_count, total_size, update_time 的对象。
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
     * 用途说明：切换展示状态为“计算中”，替换文字内容并激活按钮旋转动画。
     */
    setLoadingState() {
        if (this.elements.btnCalc) this.elements.btnCalc.classList.add('rotating');
    },

    /**
     * 用途说明：清除“计算中”加载状态。
     */
    clearLoadingState() {
        if (this.elements.btnCalc) this.elements.btnCalc.classList.remove('rotating');
    },

    /**
     * 用途说明：显示隐藏的测试入口。
     */
    showTestMenu() {
        if (this.elements.testPageMenu) {
            this.elements.testPageMenu.classList.remove('hidden');
            Toast.show('测试模式已开启~');
        }
    }
};

// --- API 交互模块 ---
const HomeAPI = {
    /**
     * 用途说明：从后端获取文件仓库详情统计。
     * 返回值说明：Promise<Object> - 后端响应结果。
     */
    async getRepoDetail() {
        return await Request.get('/api/file_repository/detail');
    },

    /**
     * 用途说明：手动触发后端重新计算文件仓库统计。
     * 逻辑说明：显式设置 showMask 为 false，以支持首页自定义的“计算中”UI 反馈。
     * 返回值说明：Promise<Object> - 后端响应结果。
     */
    async calculateRepoDetail() {
        return await Request.post('/api/file_repository/detail/calculate', {}, {}, false);
    },

    /**
     * 用途说明：从后端获取应用版本号。
     * 返回值说明：Promise<Object> - 后端响应结果。
     */
    async getAppVersion() {
        return await Request.get('/api/system/version', {}, false); // showMask is false for version fetching
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用，绑定事件并加载初始数据。
     * 补充说明：现在还会获取并显示应用版本号。
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadRepoStats();
        this.fetchAndDisplayAppVersion(); // Add this line
    },

    /**
     * 用途说明：页面初始化时加载并展示仓库统计数据。
     */
    async loadRepoStats() {
        const response = await HomeAPI.getRepoDetail();
        if (response.status === 'success') {
            UIController.updateStatsUI(response.data);
        }
    },

    /**
     * 用途说明：处理“计算”按钮点击事件。
     */
    async handleCalculateStats() {
        // 1. 切换 UI 至加载状态
        UIController.setLoadingState();

        try {
            // 2. 发起计算请求（已配置不显示全局蒙版）
            const response = await HomeAPI.calculateRepoDetail();
            
            // 3. 恢复 UI 状态
            UIController.clearLoadingState();
            
            if (response.status === 'success') {
                Toast.show('仓库数据统计已更新');
                UIController.updateStatsUI(response.data);
            } else {
                Toast.show(response.message || '计算失败');
                this.loadRepoStats(); // 失败时尝试恢复展示旧数据
            }
        } catch (error) {
            UIController.clearLoadingState();
            this.loadRepoStats();
        }
    },

    /**
     * 用途说明：获取并显示应用版本号。
     */
    async fetchAndDisplayAppVersion() {
        const response = await HomeAPI.getAppVersion();
        if (response.status === 'success' && response.data && response.data.version) {
            const versionDisplay = document.getElementById('app-version-display');
            if (versionDisplay) {
                versionDisplay.textContent = `版本: ${response.data.version}`;
            }
        } else {
            console.error('Failed to fetch app version:', response.message);
        }
    },

    /**
     * 用途说明：注销登录逻辑，清除本地状态并跳转。
     */
    logout() {
        UIComponents.showConfirmModal({
            title: '确认退出',
            message: '确定要退出登录并返回登录页面吗？',
            confirmText: '确定退出',
            onConfirm: () => {
                Request.post('/api/logout', {}).catch(err => console.error('Logout failed:', err));
                Request.eraseCookie('token');
                window.location.href = '../login/login.html';
            }
        });
    },

    /**
     * 用途说明：绑定页面交互事件，包括功能卡片导航和统计刷新。
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
                    'menu-test-page': '../test_page/test_progress_button.html'
                };
                const target = map[card.id];
                if (target) window.location.href = target;
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
