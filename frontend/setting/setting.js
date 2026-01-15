/**
 * 用途：系统设置页面逻辑，负责加载和保存后端配置，处理选项卡切换和仓库管理
 */
let currentFileRepository = {
    directories: [],
    scan_suffixes: ["*"],
    search_replace_chars: [],
    ignore_filenames: [],
    ignore_filenames_case_insensitive: true,
    ignore_paths: [],
    ignore_paths_case_insensitive: true,
    thumbnail_size: 256,
    quick_view_thumbnail: false
}; // 存储本地修改中的文件仓库配置

let currentDuplicateCheck = {
    image_threshold: 8,
    video_frame_similar_distance: 5,
    video_frame_similarity_rate: 0.7,
    video_interval_seconds: 30,
    video_max_duration_diff_ratio: 0.6
}; // 存储查重配置

document.addEventListener('DOMContentLoaded', () => {
    // 初始化公用头部
    UIComponents.initHeader('系统设置');

    initTabs();
    loadSettings();

    // 绑定仓库管理相关事件
    document.getElementById('add-repo-btn').addEventListener('click', addRepository);
    document.getElementById('save-repo-btn').addEventListener('click', saveFileRepositorySettings);
    
    // 绑定查重配置保存按钮
    document.getElementById('save-dup-check-btn').addEventListener('click', saveDuplicateCheckSettings);

    // 绑定清空视频特征库按钮
    const clearVideoBtn = document.getElementById('clear-video-btn');
    if (clearVideoBtn) {
        clearVideoBtn.addEventListener('click', () => showClearVideoFeaturesModal());
    }

    // 绑定清空历史库按钮
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', () => showClearHistoryModal());
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
    const tabs = [
        { btn: 'tab-repo', content: 'content-repo' },
        { btn: 'tab-dup-check', content: 'content-dup-check' },
        { btn: 'tab-password', content: 'content-password' }
    ];

    tabs.forEach(tab => {
        const btnElement = document.getElementById(tab.btn);
        if (btnElement) {
            btnElement.addEventListener('click', () => {
                // 移除所有激活状态
                tabs.forEach(t => {
                    document.getElementById(t.btn).classList.remove('active');
                    document.getElementById(t.content).classList.remove('active');
                });
                // 激活当前点击的
                document.getElementById(tab.btn).classList.add('active');
                document.getElementById(tab.content).classList.add('active');
            });
        }
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
                search_replace_chars: [],
                ignore_filenames: [],
                ignore_filenames_case_insensitive: true,
                ignore_paths: [],
                ignore_paths_case_insensitive: true,
                thumbnail_size: 256,
                quick_view_thumbnail: false
            };
            
            // 填充输入框
            document.getElementById('scan-suffixes').value = (currentFileRepository.scan_suffixes || ["*"]).join(', ');
            document.getElementById('thumbnail-size').value = currentFileRepository.thumbnail_size || 256;
            document.getElementById('quick-view-thumbnail').checked = currentFileRepository.quick_view_thumbnail || false;
            document.getElementById('ignore-filenames').value = (currentFileRepository.ignore_filenames || []).join(', ');
            document.getElementById('ignore-filenames-case-insensitive').checked = currentFileRepository.ignore_filenames_case_insensitive;
            document.getElementById('ignore-paths').value = (currentFileRepository.ignore_paths || []).join(', ');
            document.getElementById('ignore-paths-case-insensitive').checked = currentFileRepository.ignore_paths_case_insensitive;
            document.getElementById('search-replace-chars').value = (currentFileRepository.search_replace_chars || []).join(', ');
            
            // 填充查重配置
            currentDuplicateCheck = data.duplicate_check || currentDuplicateCheck;
            document.getElementById('image-threshold').value = currentDuplicateCheck.image_threshold;
            document.getElementById('video-frame-similar-distance').value = currentDuplicateCheck.video_frame_similar_distance;
            document.getElementById('video-frame-similarity-rate').value = currentDuplicateCheck.video_frame_similarity_rate;
            document.getElementById('video-interval-seconds').value = currentDuplicateCheck.video_interval_seconds;
            document.getElementById('video-max-duration-diff-ratio').value = currentDuplicateCheck.video_max_duration_diff_ratio;

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
        listContainer.innerHTML = '<div class="empty-hint-text">暂无仓库路径</div>';
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

    // 获取并处理缩略图尺寸
    const thumbSize = parseInt(document.getElementById('thumbnail-size').value);
    if (isNaN(thumbSize) || thumbSize <= 0) {
        Toast.show('缩略图尺寸必须是正整数');
        return;
    }

    const quickViewThumbnail = document.getElementById('quick-view-thumbnail').checked;

    // 获取并处理忽略列表
    const ignoreFilenamesInput = document.getElementById('ignore-filenames').value;
    const ignoreFilenames = ignoreFilenamesInput.split(',')
        .map(s => s.trim())
        .filter(s => s !== '');
    const ignoreFilenamesCaseInsensitive = document.getElementById('ignore-filenames-case-insensitive').checked;
        
    const ignorePathsInput = document.getElementById('ignore-paths').value;
    const ignorePaths = ignorePathsInput.split(',')
        .map(s => s.trim())
        .filter(s => s !== '');
    const ignorePathsCaseInsensitive = document.getElementById('ignore-paths-case-insensitive').checked;

    // 获取并处理替换字符列表
    const replaceCharsInput = document.getElementById('search-replace-chars').value;
    const replaceChars = replaceCharsInput.split(',')
        .map(s => s.trim())
        .filter(s => s !== '');

    currentFileRepository.scan_suffixes = suffixes;
    currentFileRepository.thumbnail_size = thumbSize;
    currentFileRepository.quick_view_thumbnail = quickViewThumbnail;
    currentFileRepository.ignore_filenames = ignoreFilenames;
    currentFileRepository.ignore_filenames_case_insensitive = ignoreFilenamesCaseInsensitive;
    currentFileRepository.ignore_paths = ignorePaths;
    currentFileRepository.ignore_paths_case_insensitive = ignorePathsCaseInsensitive;
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
 * 用途：提交修改后的查重配置到后端
 * 入参说明：无
 * 返回值说明：无
 */
async function saveDuplicateCheckSettings() {
    const imageThreshold = parseInt(document.getElementById('image-threshold').value);
    const videoDist = parseInt(document.getElementById('video-frame-similar-distance').value);
    const videoRate = parseFloat(document.getElementById('video-frame-similarity-rate').value);
    const videoInterval = parseInt(document.getElementById('video-interval-seconds').value);
    const videoDurationRatio = parseFloat(document.getElementById('video-max-duration-diff-ratio').value);

    if (isNaN(imageThreshold) || isNaN(videoDist) || isNaN(videoRate) || isNaN(videoInterval) || isNaN(videoDurationRatio)) {
        Toast.show('请确保所有查重参数输入正确且为数字');
        return;
    }

    const dupConfig = {
        image_threshold: imageThreshold,
        video_frame_similar_distance: videoDist,
        video_frame_similarity_rate: videoRate,
        video_interval_seconds: videoInterval,
        video_max_duration_diff_ratio: videoDurationRatio
    };

    // 检查采样间隔是否被修改
    if (videoInterval !== currentDuplicateCheck.video_interval_seconds) {
        UIComponents.showConfirmModal({
            title: '确认修改采样间隔',
            message: '修改采样间隔会导致现有的视频特征数据失效，必须清空视频特征库后才能保存。确定要清空并保存吗？',
            onConfirm: async () => {
                try {
                    // 1. 调用清空视频特征库 API
                    const clearRes = await Request.post('/api/file_repository/clear_video_features');
                    if (clearRes.status === 'success') {
                        // 2. 调用保存配置 API
                        await executeSaveDuplicateCheck(dupConfig);
                    } else {
                        Toast.show('清空视频特征库失败，取消保存配置: ' + clearRes.message);
                    }
                } catch (error) {
                    Toast.show('清空视频特征库请求失败: ' + (error.message || '未知错误'));
                }
            }
        });
    } else {
        await executeSaveDuplicateCheck(dupConfig);
    }
}

/**
 * 用途说明：实际执行保存查重配置的请求
 * 入参说明：dupConfig (object) - 查重配置对象
 * 返回值说明：无
 */
async function executeSaveDuplicateCheck(dupConfig) {
    try {
        const response = await Request.post('/api/setting/update', {
            duplicate_check: dupConfig
        });
        if (response.status === 'success') {
            Toast.show('查重配置保存成功');
            loadSettings();
        }
    } catch (error) {
        Toast.show('保存查重配置失败: ' + (error.message || '未知错误'));
    }
}

/**
 * 用途说明：显示确认清空视频特征库弹窗
 * 返回值说明：无
 */
function showClearVideoFeaturesModal() {
    UIComponents.showConfirmModal({
                title: '确认清空视频特征库',
                message: '警告：此操作将清空所有视频特征指纹库（用于视频查重），确定要继续吗？',
                onConfirm: () => {
                    clearVideoFeaturesDatabase();
                }
            });
}

/**
 * 用途说明：显示确认清空历史库弹窗
 * 返回值说明：无
 */
function showClearHistoryModal() {
    UIComponents.showConfirmModal({
        title: '确认清空历史库',
        message: '警告：此操作将永久清空所有历史索引记录（history_file_index），确定要继续吗？',
        onConfirm: () => {
            clearHistoryRepositoryDatabase();
        }
    });
}

/**
 * 用途说明：向后端发起请求清空文件索引数据库
 * 入参说明：clearHistory (bool) - 是否同时清空历史记录
 * 返回值说明：无
 */
async function clearFileRepositoryDatabase(clearHistory) {
    try {
        const response = await Request.post('/api/file_repository/clear', {
            clear_history: clearHistory
        });
        if (response.status === 'success') {
            Toast.show(response.message || '文件数据库已成功清空');
        } else {
            Toast.show('清空失败: ' + response.message);
        }
    } catch (error) {
        console.error('清空数据库出错:', error);
        Toast.show('网络请求失败');
    }
}

/**
 * 用途说明：向后端发起请求清空历史记录库
 * 入参说明：无
 * 返回值说明：无
 */
async function clearHistoryRepositoryDatabase() {
    try {
        const response = await Request.post('/api/file_repository/clear_history');
        if (response.status === 'success') {
            Toast.show(response.message || '历史记录库已成功清空');
        } else {
            Toast.show('清空失败: ' + response.message);
        }
    } catch (error) {
        console.error('清空历史记录库出错:', error);
        Toast.show('网络请求失败');
    }
}

/**
 * 用途说明：向后端发起请求清空视频特征库
 * 入参说明：无
 * 返回值说明：无
 */
async function clearVideoFeaturesDatabase() {
    try {
        const response = await Request.post('/api/file_repository/clear_video_features');
        if (response.status === 'success') {
            Toast.show(response.message || '视频特征库已成功清空');
        } else {
            Toast.show('清空失败: ' + response.message);
        }
    } catch (error) {
        console.error('清空视频特征库出错:', error);
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
