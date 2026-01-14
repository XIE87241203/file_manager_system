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
        // 初始化公用头部，主页不需要返回按钮
        UIComponents.initHeader('文件管理系统', false);
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
     * 用途说明：绑定交互事件
     */
    bindEvents() {
        // 绑定卡片点击跳转逻辑
        const cards = document.querySelectorAll('.menu-item'); // 修正选择器以匹配 home.html 的 id
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
