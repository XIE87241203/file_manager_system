/**
 * 用途：首页逻辑处理，负责页面跳转和功能入口绑定
 */
document.addEventListener('DOMContentLoaded', () => {
    // 1. 获取登录用户名
    const username = sessionStorage.getItem('username') || '管理员';

    // 2. 初始化公用头部：显示欢迎语，并在右侧放置登出按钮
    UIComponents.initHeader(
        `欢迎你，${username}`, 
        false, 
        null, 
        '退出登录', 
        handleLogoutAction
    );

    // 3. 绑定功能菜单跳转
    bindMenuAction('menu-file-repository', '../file_repository/file_repository.html');
    bindMenuAction('menu-duplicate-check', '../file_repository/duplicate_check/duplicate_check.html');
    bindMenuAction('menu-setting', '../setting/setting.html');
    
    // 4. 绑定特殊功能或提示
    const menuLogs = document.getElementById('menu-logs');
    if (menuLogs) {
        menuLogs.onclick = () => Toast.show('功能开发中...');
    }
});

/**
 * 用途说明：封装统一的菜单跳转绑定逻辑
 * 入参说明：id - 元素的 ID, url - 跳转的目标路径
 * 返回值说明：无
 */
function bindMenuAction(id, url) {
    const element = document.getElementById(id);
    if (element) {
        element.onclick = () => {
            window.location.href = url;
        };
    }
}

/**
 * 用途说明：统一的退出登录处理逻辑
 * 入参说明：无
 * 返回值说明：无
 */
function handleLogoutAction() {
    if (confirm('确定要退出登录吗？')) {
        // 1. 发起后端注销请求（忽略失败）
        Request.post('/api/logout').catch(err => {
            console.error('后端注销接口调用失败:', err);
        });

        // 2. 清除本地认证信息
        Request.eraseCookie('token');
        sessionStorage.removeItem('username'); // 同时清除用户名缓存

        // 3. 立即跳转到登录页面
        window.location.href = '../login/login.html';
    }
}
