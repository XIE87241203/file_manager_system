/**
 * 用途：首页逻辑处理，负责页面跳转和功能入口绑定
 */
document.addEventListener('DOMContentLoaded', () => {
    // 初始化公用头部
    UIComponents.initHeader('控制面板', false);

    // 1. 绑定设置按钮跳转
    initMenuSetting();

    // 2. 绑定文件仓库按钮跳转
    initMenuFileRepository();

    // 3. 绑定退出登录按钮
    initMenuLogout();
});

/**
 * 用途：初始化系统设置菜单项的点击事件
 * 入参说明：无
 * 返回值说明：无
 */
function initMenuSetting() {
    const menuSetting = document.getElementById('menu-setting');
    if (menuSetting) {
        menuSetting.addEventListener('click', () => {
            window.location.href = '../setting/setting.html';
        });
    }
}

/**
 * 用途：初始化文件仓库菜单项的点击事件
 * 入参说明：无
 * 返回值说明：无
 */
function initMenuFileRepository() {
    const menuFileRepo = document.getElementById('menu-file-repository');
    if (menuFileRepo) {
        menuFileRepo.addEventListener('click', () => {
            window.location.href = '../file_repository/file_repository.html';
        });
    }
}

/**
 * 用途：初始化退出登录菜单项的点击事件，通知后端注销并立即返回登录页
 * 入参说明：无
 * 返回值说明：无
 */
function initMenuLogout() {
    const menuLogout = document.getElementById('menu-logout');
    if (menuLogout) {
        menuLogout.addEventListener('click', () => {
            if (confirm('确定要退出登录吗？')) {
                // 1. 发起后端注销请求（无需等待 api 返回，直接继续后续逻辑）
                Request.post('/api/logout').catch(err => {
                    // 仅记录日志，不阻断跳转流程
                    console.error('后端注销接口调用失败:', err);
                });

                // 2. 清除本地保存的认证信息
                sessionStorage.removeItem('token');

                // 3. 立即跳转到登录页面
                window.location.href = '../login/login.html';
            }
        });
    }
}
