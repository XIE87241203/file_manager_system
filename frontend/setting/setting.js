/**
 * 用途：系统设置页面逻辑，负责加载和保存后端配置，处理选项卡切换和仓库管理
 */
let currentFileRepository = {
    directories: [],
    scan_suffixes: ["*"],
    search_replace_chars: []
}; // 存储本地修改中的文件仓库配置

document.addEventListener('DOMContentLoaded', () => {
    // 初始化公用头部
    UIComponents.initHeader('系统设置');

    initTabs();
    loadSettings();

    // 绑定仓库管理相关事件
    document.getElementById('add-repo-btn').addEventListener('click', addRepository);
    document.getElementById('save-repo-btn').addEventListener('click', saveFileRepositorySettings);
    
    // 绑定清空数据库按钮
    const clearDbBtn = document.getElementById('clear-db-btn');
    if (clearDbBtn) {
        clearDbBtn.addEventListener('click', clearFileRepositoryDatabase);
    }
    
    // 绑定修改密码保存按钮
    document.getElementById('save-pwd-btn').addEventListener('click', savePasswordSettings);
});

/**
 * 用途：初始化选项卡切换逻辑
 * 入参说明：无
 * 返回值说明：无
 */
function initTabs() {
    const tabRepo = document.getElementById('tab-repo');
    const tabPassword = document.getElementById('tab-password');
    const contentRepo = document.getElementById('content-repo');
    const contentPassword = document.getElementById('content-password');

    tabRepo.addEventListener('click', () => {
        tabRepo.classList.add('active');
        tabPassword.classList.remove('active');
        contentRepo.classList.add('active');
        contentPassword.classList.remove('active');
    });

    tabPassword.addEventListener('click', () => {
        tabPassword.classList.add('active');
        tabRepo.classList.remove('active');
        contentPassword.classList.add('active');
        contentRepo.classList.remove('active');
    });
}

/**
 * 用途：从后端获取当前配置信息并填充表单和仓库列表
 * 入参说明：无
 * 返回值说明：无
 */
async function loadSettings() {
    try {
        const response = await Request.get('/api/setting/get');
        if (response.status === 'success') {
            const data = response.data;
            
            // 填充用户数据
            const userData = data.user_data;
            document.getElementById('username').value = userData.username || '';
            document.getElementById('password').value = '';
            document.getElementById('confirm-password').value = '';

            // 填充文件仓库配置
            currentFileRepository = data.file_repository || {
                directories: [],
                scan_suffixes: ["*"],
                search_replace_chars: []
            };
            
            // 填充后缀输入框
            document.getElementById('scan-suffixes').value = (currentFileRepository.scan_suffixes || ["*"]).join(', ');
            
            // 填充搜索替换字符输入框
            document.getElementById('search-replace-chars').value = (currentFileRepository.search_replace_chars || []).join(', ');
            
            renderRepositoryList();
        }
    } catch (error) {
        console.error('加载设置失败:', error);
        Toast.show('加载设置失败: ' + (error.message || '未知错误'));
    }
}

/**
 * 用途：渲染仓库路径列表到页面
 * 入参说明：无
 * 返回值说明：无
 */
function renderRepositoryList() {
    const listContainer = document.getElementById('repo-list');
    listContainer.innerHTML = '';

    const directories = currentFileRepository.directories;

    if (!directories || directories.length === 0) {
        listContainer.innerHTML = '<div style="color: #999; text-align: center; padding: 20px;">暂无仓库路径</div>';
        return;
    }

    directories.forEach((path, index) => {
        const item = document.createElement('div');
        item.className = 'repo-item';
        item.innerHTML = `
            <div class="repo-path">${path}</div>
            <div class="repo-actions">
                <button class="btn-delete" onclick="deleteRepository(${index})">删除</button>
            </div>
        `;
        listContainer.appendChild(item);
    });
}

/**
 * 用途：向本地列表中添加一个新的仓库路径
 * 入参说明：无
 * 返回值说明：无
 */
function addRepository() {
    const pathInput = document.getElementById('new-repo-path');
    const path = pathInput.value.trim();

    if (!path) {
        Toast.show('请输入仓库路径');
        return;
    }

    if (currentFileRepository.directories.includes(path)) {
        Toast.show('该路径已存在');
        return;
    }

    currentFileRepository.directories.push(path);
    pathInput.value = '';
    renderRepositoryList();
}

/**
 * 用途：从本地列表中删除指定索引的仓库路径
 * 入参说明：index - 要删除的路径在列表中的索引
 * 返回值说明：无
 */
window.deleteRepository = function(index) {
    currentFileRepository.directories.splice(index, 1);
    renderRepositoryList();
};

/**
 * 用途：提交修改后的文件仓库配置到后端
 * 入参说明：无
 * 返回值说明：无
 */
async function saveFileRepositorySettings() {
    // 获取并处理后缀列表
    const suffixesInput = document.getElementById('scan-suffixes').value;
    const suffixes = suffixesInput.split(',')
        .map(s => s.trim())
        .filter(s => s !== '');

    if (suffixes.length === 0) {
        Toast.show('扫描后缀不能为空，至少应包含 *');
        return;
    }

    // 获取并处理替换字符列表
    const replaceCharsInput = document.getElementById('search-replace-chars').value;
    const replaceChars = replaceCharsInput.split(',')
        .map(s => s.trim())
        .filter(s => s !== '');

    currentFileRepository.scan_suffixes = suffixes;
    currentFileRepository.search_replace_chars = replaceChars;

    try {
        const response = await Request.post('/api/setting/update', {
            file_repository: currentFileRepository
        });
        if (response.status === 'success') {
            Toast.show('文件仓库配置保存成功');
            loadSettings();
        }
    } catch (error) {
        Toast.show('保存仓库失败: ' + (error.message || '未知错误'));
    }
}

/**
 * 用途说明：向后端发起请求清空文件索引数据库，包含二次确认逻辑
 * 入参说明：无
 * 返回值说明：无
 */
async function clearFileRepositoryDatabase() {
    // 二次确认
    if (!confirm('警告：此操作将清空所有已扫描的文件索引数据，且不可恢复！确定要继续吗？')) {
        return;
    }

    try {
        const response = await Request.post('/api/file_repository/clear');
        if (response.status === 'success') {
            Toast.show('文件数据库已成功清空');
        } else {
            Toast.show('清空失败: ' + response.msg);
        }
    } catch (error) {
        console.error('清空数据库出错:', error);
        Toast.show('网络请求失败');
    }
}

/**
 * 用途：提交修改后的密码和用户名到后端
 * 入参说明：无
 * 返回值说明：无
 */
async function savePasswordSettings() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (!username) {
        Toast.show('用户名不能为空');
        return;
    }

    const userData = {
        username: username
    };

    // 只有当用户输入了新密码时才发送密码字段
    if (password) {
        if (password !== confirmPassword) {
            Toast.show('两次输入的密码不一致');
            return;
        }
        userData.password = password;
    }

    try {
        const response = await Request.post('/api/setting/update', {
            user_data: userData
        });
        if (response.status === 'success') {
            Toast.show('密码设置保存成功！');
            
            if (password) {
                setTimeout(() => {
                    Toast.show('检测到密码已修改，请重新登录');
                    Request.eraseCookie('token');
                    window.location.href = '../login/login.html';
                }, 1000);
            } else {
                loadSettings();
            }
        }
    } catch (error) {
        Toast.error('保存设置失败: ' + (error.message || '未知错误'));
    }
}
