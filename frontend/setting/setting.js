/**
 * 用途：系统设置页面逻辑，负责加载和保存后端配置，处理选项卡切换和仓库管理
 */

// --- 状态管理 ---
const State = {
    fileRepository: {
        directories: [],
        scan_suffixes: ["*"],
        search_replace_chars: [],
        ignore_filenames: [],
        ignore_filenames_case_insensitive: true,
        ignore_paths: [],
        ignore_paths_case_insensitive: true,
        thumbnail_size: 256,
        quick_view_thumbnail: false
    },
    duplicateCheck: {
        image_threshold: 8,
        video_frame_similar_distance: 5,
        video_frame_similarity_rate: 0.7,
        video_interval_seconds: 30,
        video_max_duration_diff_ratio: 0.6,
        video_backwards: false
    }
};

// --- API 交互模块 ---
const API = {
    /**
     * 用途说明：从后端获取系统配置
     * 返回值说明：Promise<Object> - 后端配置数据
     */
    async getSettings() {
        return await Request.get('/api/setting/get');
    },

    /**
     * 用途说明：更新后端系统配置
     * 入参说明：data (Object) - 需要更新的配置片段（file_repository, duplicate_check, 或 user_data）
     * 返回值说明：Promise<Object> - 请求结果
     */
    async updateSettings(data) {
        return await Request.post('/api/setting/update', data);
    },

    /**
     * 用途说明：清空曾录入文件名库记录
     * 返回值说明：Promise<Object> - 请求结果
     */
    async clearAlreadyEntered() {
        return await Request.post('/api/file_name_repository/already_entered/clear');
    },

    /**
     * 用途说明：清空待录入文件名库记录
     * 返回值说明：Promise<Object> - 请求结果
     */
    async clearPendingEntry() {
        return await Request.post('/api/file_name_repository/pending_entry/clear');
    },

    /**
     * 用途说明：清空历史记录库
     * 返回值说明：Promise<Object> - 请求结果
     */
    async clearHistory() {
        return await Request.post('/api/file_repository/clear_history');
    },

    /**
     * 用途说明：清空视频特征指纹库
     * 返回值说明：Promise<Object> - 请求结果
     */
    async clearVideoFeatures() {
        return await Request.post('/api/file_repository/clear_video_features');
    }
};

// --- UI 控制模块 ---
const UIController = {
    /**
     * 用途说明：初始化选项卡切换逻辑
     */
    initTabs() {
        const tabs = [
            { btn: 'tab-repo', content: 'content-repo' },
            { btn: 'tab-dup-check', content: 'content-dup-check' },
            { btn: 'tab-maintenance', content: 'content-maintenance' },
            { btn: 'tab-password', content: 'content-password' }
        ];

        tabs.forEach(tab => {
            const btnElement = document.getElementById(tab.btn);
            if (btnElement) {
                btnElement.onclick = () => {
                    tabs.forEach(t => {
                        const b = document.getElementById(t.btn);
                        const c = document.getElementById(t.content);
                        if (b) b.classList.remove('active');
                        if (c) c.classList.remove('active');
                    });
                    document.getElementById(tab.btn).classList.add('active');
                    document.getElementById(tab.content).classList.add('active');
                };
            }
        });
    },

    /**
     * 用途说明：将配置数据填充到表单输入框中
     * 入参说明：data (Object) - 后端返回的配置总览数据
     */
    fillSettingsForm(data) {
        // 用户数据
        const userData = data.user_data || {};
        document.getElementById('username').value = userData.username || '';
        document.getElementById('password').value = '';
        document.getElementById('confirm-password').value = '';

        // 文件仓库配置同步到 State
        State.fileRepository = data.file_repository || State.fileRepository;
        const fr = State.fileRepository;
        document.getElementById('scan-suffixes').value = (fr.scan_suffixes || ["*"]).join(', ');
        document.getElementById('thumbnail-size').value = fr.thumbnail_size || 256;
        document.getElementById('quick-view-thumbnail').checked = fr.quick_view_thumbnail || false;
        document.getElementById('ignore-filenames').value = (fr.ignore_filenames || []).join(', ');
        document.getElementById('ignore-filenames-case-insensitive').checked = fr.ignore_filenames_case_insensitive;
        document.getElementById('ignore-paths').value = (fr.ignore_paths || []).join(', ');
        document.getElementById('ignore-paths-case-insensitive').checked = fr.ignore_paths_case_insensitive;
        document.getElementById('search-replace-chars').value = (fr.search_replace_chars || []).join(', ');

        // 查重配置同步到 State
        State.duplicateCheck = data.duplicate_check || State.duplicateCheck;
        const dc = State.duplicateCheck;
        document.getElementById('image-threshold').value = dc.image_threshold;
        document.getElementById('video-frame-similar-distance').value = dc.video_frame_similar_distance;
        document.getElementById('video-frame-similarity-rate').value = dc.video_frame_similarity_rate;
        document.getElementById('video-interval-seconds').value = dc.video_interval_seconds;
        document.getElementById('video-max-duration-diff-ratio').value = dc.video_max_duration_diff_ratio;
        document.getElementById('video-backwards').checked = dc.video_backwards || false;

        this.renderRepositoryList();
    },

    /**
     * 用途说明：渲染仓库路径列表
     */
    renderRepositoryList() {
        const listContainer = document.getElementById('repo-list');
        listContainer.innerHTML = '';
        const directories = State.fileRepository.directories;

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
                    <button class="btn-delete" data-index="${index}">删除</button>
                </div>
            `;
            // 绑定删除按钮点击事件
            item.querySelector('.btn-delete').onclick = () => App.handleDeleteRepository(index);
            listContainer.appendChild(item);
        });
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用
     */
    init() {
        UIComponents.initHeader('系统设置', true, null, '保存', () => this.handleGlobalSave());
        UIController.initTabs();
        this.loadSettings();
        this.bindEvents();
    },

    /**
     * 用途说明：绑定页面交互事件
     */
    bindEvents() {
        document.getElementById('add-repo-btn').onclick = () => this.handleAddRepository();

        // 危险操作按钮
        document.getElementById('clear-already-entered-btn').onclick = () => this.confirmClear('already_entered');
        document.getElementById('clear-pending-entry-btn').onclick = () => this.confirmClear('pending_entry');
        document.getElementById('clear-history-btn').onclick = () => this.confirmClear('history');
        document.getElementById('clear-video-btn').onclick = () => this.confirmClear('video');
    },

    /**
     * 用途说明：加载后端配置并渲染
     */
    async loadSettings() {
        try {
            const res = await API.getSettings();
            if (res.status === 'success') {
                UIController.fillSettingsForm(res.data);
            }
        } catch (e) {
            Toast.show('加载设置失败: ' + e.message);
        }
    },

    /**
     * 用途说明：添加仓库路径（弹窗录入模式）
     * 入参说明：无
     * 返回值说明：无
     */
    handleAddRepository() {
        UIComponents.showInputModal({
            title: '添加仓库路径',
            placeholder: '请输入文件仓库绝对路径',
            onConfirm: (value) => {
                const path = value.trim();
                if (!path) {
                    Toast.show('路径不能为空');
                    return;
                }
                if (State.fileRepository.directories.includes(path)) {
                    Toast.show('该路径已存在');
                    return;
                }
                State.fileRepository.directories.push(path);
                UIController.renderRepositoryList();
                Toast.show('已添加到本地列表，请记得点击顶栏“保存”哦~');
            }
        });
    },

    /**
     * 用途说明：从本地列表删除仓库路径
     * 入参说明：index (number) - 待删除路径的索引
     */
    handleDeleteRepository(index) {
        State.fileRepository.directories.splice(index, 1);
        UIController.renderRepositoryList();
    },

    /**
     * 用途说明：一次性保存全站设置（包括仓库配置、查重配置和用户信息）
     * 入参说明：无
     * 返回值说明：无
     */
    async handleGlobalSave() {
        // 1. 采集文件仓库数据
        const fr = State.fileRepository;
        fr.scan_suffixes = document.getElementById('scan-suffixes').value.split(',').map(s => s.trim()).filter(s => s);
        fr.thumbnail_size = parseInt(document.getElementById('thumbnail-size').value);
        fr.quick_view_thumbnail = document.getElementById('quick-view-thumbnail').checked;
        fr.ignore_filenames = document.getElementById('ignore-filenames').value.split(',').map(s => s.trim()).filter(s => s);
        fr.ignore_filenames_case_insensitive = document.getElementById('ignore-filenames-case-insensitive').checked;
        fr.ignore_paths = document.getElementById('ignore-paths').value.split(',').map(s => s.trim()).filter(s => s);
        fr.ignore_paths_case_insensitive = document.getElementById('ignore-paths-case-insensitive').checked;
        fr.search_replace_chars = document.getElementById('search-replace-chars').value.split(',').map(s => s.trim()).filter(s => s);

        if (fr.scan_suffixes.length === 0) {
            Toast.show('扫描后缀不能为空');
            return;
        }

        // 2. 采集查重配置数据
        const dc = {
            image_threshold: parseInt(document.getElementById('image-threshold').value),
            video_frame_similar_distance: parseInt(document.getElementById('video-frame-similar-distance').value),
            video_frame_similarity_rate: parseFloat(document.getElementById('video-frame-similarity-rate').value),
            video_interval_seconds: parseInt(document.getElementById('video-interval-seconds').value),
            video_max_duration_diff_ratio: parseFloat(document.getElementById('video-max-duration-diff-ratio').value),
            video_backwards: document.getElementById('video-backwards').checked
        };

        // 3. 采集用户信息数据
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;

        if (!username) {
            Toast.show('用户名不能为空');
            return;
        }

        const userData = { username };
        let isPasswordChanged = false;
        if (password) {
            if (password !== confirmPassword) {
                Toast.show('两次输入的密码不一致');
                return;
            }
            userData.password = password;
            isPasswordChanged = true;
        }

        const updateData = {
            file_repository: fr,
            duplicate_check: dc,
            user_data: userData
        };

        // 4. 查重核心参数变更检查
        const isIntervalChanged = dc.video_interval_seconds !== State.duplicateCheck.video_interval_seconds;
        const isBackwardsChanged = dc.video_backwards !== State.duplicateCheck.video_backwards;

        if (isIntervalChanged || isBackwardsChanged) {
            UIComponents.showConfirmModal({
                title: '确认修改核心参数',
                message: '修改视频采样间隔或方向将导致现有视频特征失效，必须清空视频特征库。确定继续吗？',
                onConfirm: async () => {
                    const clearRes = await API.clearVideoFeatures();
                    if (clearRes.status === 'success') {
                        await this.executeGlobalSave(updateData, isPasswordChanged);
                    }
                }
            });
        } else {
            await this.executeGlobalSave(updateData, isPasswordChanged);
        }
    },

    /**
     * 用途说明：执行全局保存请求
     * 入参说明：updateData (Object) - 合并后的更新配置数据, isPasswordChanged (boolean) - 标识是否修改了密码
     * 返回值说明：无
     */
    async executeGlobalSave(updateData, isPasswordChanged) {
        try {
            const res = await API.updateSettings(updateData);
            if (res.status === 'success') {
                Toast.show('系统设置已全部保存成功');
                
                if (isPasswordChanged) {
                    setTimeout(() => {
                        Toast.show('检测到密码已修改，请重新登录');
                        Request.eraseCookie('token');
                        window.location.href = '../login/login.html';
                    }, 1000);
                } else {
                    this.loadSettings();
                }
            }
        } catch (e) {
            Toast.show('保存失败: ' + e.message);
        }
    },

    /**
     * 用途说明：统一处理清空库的二次确认逻辑
     * 入参说明：type (string) - 类型：already_entered, pending_entry, history, video
     */
    confirmClear(type) {
        const config = {
            already_entered: { title: '确认清空曾录入文件名库', msg: '确定要清空所有曾录入文件名吗？', api: API.clearAlreadyEntered },
            pending_entry: { title: '确认清空待录入文件名库', msg: '确定要清空所有待录入文件名吗？', api: API.clearPendingEntry },
            history: { title: '确认清空历史库', msg: '这将永久清空所有历史索引记录，确定吗？', api: API.clearHistory },
            video: { title: '确认清空视频特征库', msg: '这将清空所有视频指纹数据，确定吗？', api: API.clearVideoFeatures }
        };
        const item = config[type];
        UIComponents.showConfirmModal({
            title: item.title,
            message: item.msg,
            onConfirm: async () => {
                const res = await item.api();
                if (res.status === 'success') {
                    Toast.show(res.message || '操作成功');
                }
            }
        });
    }
};

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', () => App.init());
