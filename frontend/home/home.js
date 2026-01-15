/**
 * 用途说明：主页逻辑处理，负责展示系统概览信息及导航
 */

// --- 状态管理 ---
const HomeState = {
    // 预留状态空间
};

// --- UI 控制模块 ---
const UIController = {
    /**
     * 用途说明：初始化页面 UI
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
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用
     */
    init() {
        UIController.init();
        this.bindEvents();
    },

    /**
     * 用途说明：执行退出登录逻辑。发起后端注销请求（不等待返回），立即清除本地 Token 并跳转至登录页面。
     * 返回值说明：无
     */
    logout() {
        UIComponents.showConfirmModal({
            title: '确认退出',
            message: '确定要退出登录并返回登录页面吗？',
            confirmText: '确定退出',
            cancelText: '取消',
            onConfirm: () => {
                // 发起后端注销 API 请求。修正路径：后端 auth_bp 挂载于 /api 下，路由为 /logout
                Request.post('/api/logout', {}).catch(err => {
                    // 仅静默记录错误，不干扰用户跳转流程
                    console.error('Logout API background task failed:', err);
                });

                // 立即执行本地清理逻辑
                Request.eraseCookie('token');
                
                // 立即执行页面跳转
                window.location.href = '../login/login.html';
            }
        });
    },

    /**
     * 用途说明：绑定页面交互事件
     */
    bindEvents() {
        // 绑定功能卡片点击跳转逻辑
        const cards = document.querySelectorAll('.menu-item');
        cards.forEach(card => {
            card.onclick = () => {
                const id = card.id;
                let target = '';
                
                switch(id) {
                    case 'menu-file-repository':
                        target = '../file_repository/file_repository.html';
                        break;
                    case 'menu-duplicate-check':
                        target = '../file_repository/duplicate_check/duplicate_check.html';
                        break;
                    case 'menu-ignore-file':
                        target = '../file_repository/ignore_file/ignore_file.html';
                        break;
                    case 'menu-recycle-bin':
                        target = '../file_repository/recycle_bin/recycle_bin.html';
                        break;
                    case 'menu-setting':
                        target = '../setting/setting.html';
                        break;
                    case 'menu-logs':
                        target = '../system/logs/logs.html';
                        break;
                }

                if (target) {
                    window.location.href = target;
                }
            };
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
