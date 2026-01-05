/**
 * 用途说明：查重页面逻辑处理，负责触发查重任务、进度监控以及查重结果的展示与交互。
 */

// --- 状态管理 ---
const CheckState = {
    results: [],
    lastCheckTime: '--',
    pollingInterval: null,

    /**
     * 用途说明：更新结果列表并更新最后检查时间
     * 入参说明：newResults (Array) - 新的结果列表
     * 返回值说明：无
     */
    setResults(newResults) {
        this.results = newResults || [];
        this.updateLastCheckTime();
    },

    /**
     * 用途说明：更新最后检查时间的字符串表示（当前时间）
     * 入参说明：无
     * 返回值说明：无
     */
    updateLastCheckTime() {
        const now = new Date();
        const y = now.getFullYear();
        const m = String(now.getMonth() + 1).padStart(2, '0');
        const d = String(now.getDate()).padStart(2, '0');
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        this.lastCheckTime = `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
    }
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，缓存常用的 DOM 元素
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        this.elements = {
            wrapper: document.getElementById('results-wrapper'),
            scanningContainer: document.getElementById('scanning-container'),
            resultsGroup: document.getElementById('results-group'),
            emptyHint: document.getElementById('empty-hint'),
            summaryBar: document.getElementById('results-summary-bar'),
            summaryGroups: document.getElementById('summary-groups'),
            summaryFiles: document.getElementById('summary-files'),
            summaryTime: document.getElementById('summary-time'),
            floatingBar: document.getElementById('floating-action-bar'),
            globalDeleteBtn: document.getElementById('btn-delete-selected-global')
        };
        this.renderHeader('idle');
    },

    /**
     * 用途说明：渲染顶部导航栏，根据任务状态切换“开始”与“停止”按钮
     * 入参说明：status (String) - 'idle' 或 'checking'
     * 返回值说明：无
     */
    renderHeader(status) {
        if (typeof UIComponents !== 'undefined') {
            const title = '文件查重';
            if (status === 'checking') {
                UIComponents.initHeader(title, true, null, '停止查重', () => DuplicateCheckAPI.stop(), 'btn-text-danger');
            } else {
                UIComponents.initHeader(title, true, null, '开始查重', () => DuplicateCheckAPI.start());
            }
        }
    },

    /**
     * 用途说明：切换页面视图状态（查重中、显示结果、显示初始引导）
     * 入参说明：status (String) - 任务状态（idle, checking, completed）
     * 返回值说明：无
     */
    toggleView(status) {
        const { scanningContainer, resultsGroup, emptyHint } = this.elements;
        if (status === 'checking') {
            this.renderHeader('checking');
            scanningContainer.style.display = 'flex';
            resultsGroup.style.display = 'none';
            emptyHint.style.display = 'none';
            // 使用封装的公共进度条组件
            UIComponents.showProgressBar('#scanning-container', '正在准备扫描...');
        } else {
            this.renderHeader('idle');
            scanningContainer.style.display = 'none';
            UIComponents.hideProgressBar('#scanning-container');
            
            // 核心修复逻辑：如果是查重完成状态，或者当前内存中已有结果数据，则必须显示结果区域
            if (status === 'completed' || (CheckState.results && CheckState.results.length > 0)) {
                resultsGroup.style.display = 'flex';
                emptyHint.style.display = 'none';
            } else {
                // 只有在空闲且无数据时才显示引导提示
                resultsGroup.style.display = 'none';
                emptyHint.style.display = (status === 'idle') ? 'block' : 'none';
            }
        }
    },

    /**
     * 用途说明：更新扫描进度条和状态文字
     * 入参说明：progress (Object) - 进度数据
     * 返回值说明：无
     */
    updateProgress(progress) {
        const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
        const text = `${progress.status_text} (${percent}%)`;
        // 使用封装的公共进度条组件更新
        UIComponents.updateProgressBar('#scanning-container', percent, text);
    },

    /**
     * 用途说明：全量渲染查重结果列表及统计栏
     * 入参说明：无
     * 返回值说明：无
     */
    renderResults() {
        const { wrapper, summaryBar, summaryGroups, summaryFiles, summaryTime } = this.elements;
        wrapper.innerHTML = '';

        const results = CheckState.results;
        // 如果查重完成但没有发现重复文件
        if (!results || results.length === 0) {
            summaryBar.style.display = 'none';
            wrapper.innerHTML = '<div style="text-align: center; color: #9aa0a6; padding-top: 100px;">未发现重复文件</div>';
            this.updateFloatingBar();
            return;
        }

        // 更新统计栏信息
        summaryBar.style.display = 'block';
        summaryGroups.textContent = `分组: ${results.length}`;
        const totalFiles = results.reduce((acc, g) => acc + (g.files ? g.files.length : 0), 0);
        summaryFiles.textContent = `文件: ${totalFiles}`;
        summaryTime.textContent = `查重时间: ${CheckState.lastCheckTime}`;

        // 遍历并渲染每一个重复组
        results.forEach(group => {
            const groupEl = this.createGroupElement(group);
            wrapper.appendChild(groupEl);
        });

        this.updateFloatingBar();
    },

    /**
     * 用途说明：创建一个重复分组的 DOM 元素
     * 入参说明：group (Object) - 分组数据
     * 返回值说明：HTMLElement - 分组节点
     */
    createGroupElement(group) {
        const groupEl = document.createElement('div');
        groupEl.className = `duplicate-group ${group.isExpanded ? 'expanded' : ''}`;
        groupEl.setAttribute('data-group-id', group.group_id);
        
        // 注意：后端数据类 DuplicateGroup 包含 files 数组
        const fileCount = group.files ? group.files.length : 0;
        const groupType = group.checker_type === 'video_similarity' ? '视频相似组' : '重复组';

        groupEl.innerHTML = `
            <div class="group-header">
                <div class="group-info">
                    <span class="group-title">${groupType}</span>
                    <span class="group-count">${fileCount} 个文件</span>
                    <span class="group-md5">ID: ${group.group_id}</span>
                </div>
                <div class="group-actions">
                    <span class="expand-icon">▶</span>
                </div>
            </div>
            <div class="group-content">
                <table class="file-item-table">
                    <thead>
                        <tr>
                            <th style="width: 25%;">文件名</th>
                            <th style="width: 70%;">完整路径</th>
                            <th style="width: 30px; text-align: center;">
                                <input type="checkbox" class="select-all-in-group">
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        ${group.files.map(f => {
                            const extra = f.extra_info && f.extra_info.duration ? ` [${f.extra_info.duration}s]` : '';
                            return `
                                <tr class="clickable-row">
                                    <td style="width: 25%;" title="${f.file_name}">${f.file_name}${extra}</td>
                                    <td style="width: 70%;" class="file-path" title="${f.file_path}">${f.file_path}</td>
                                    <td style="width: 30px; text-align: center;">
                                        <input type="checkbox" class="file-checkbox" data-path="${f.file_path}">
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;

        // 绑定折叠/展开事件
        groupEl.querySelector('.group-header').addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            const isExpanded = groupEl.classList.toggle('expanded');
            group.isExpanded = isExpanded;
        });

        // 绑定组内全选事件
        const selectAllCheckbox = groupEl.querySelector('.select-all-in-group');
        const fileCheckboxes = groupEl.querySelectorAll('.file-checkbox');
        selectAllCheckbox.onchange = (e) => {
            const isChecked = selectAllCheckbox.checked;
            fileCheckboxes.forEach(cb => {
                cb.checked = isChecked;
                const row = cb.closest('tr');
                if (isChecked) row.classList.add('selected-row');
                else row.classList.remove('selected-row');
            });
            this.updateFloatingBar();
        };

        // 绑定行点击选择事件 (符合 AGENTS.md 规范)
        groupEl.querySelectorAll('.clickable-row').forEach(tr => {
            tr.addEventListener('click', (e) => {
                const cb = tr.querySelector('.file-checkbox');
                let isChecked;
                if (e.target !== cb) {
                    cb.checked = !cb.checked;
                }
                isChecked = cb.checked;
                
                // 更新行背景
                if (isChecked) tr.classList.add('selected-row');
                else tr.classList.remove('selected-row');

                // 如果取消选中，同步取消组全选框的状态
                if (!isChecked) {
                    selectAllCheckbox.checked = false;
                }
                
                this.updateFloatingBar();
            });
        });

        return groupEl;
    },

    /**
     * 用途说明：更新底部浮动操作栏的显示状态及选中计数
     * 入参说明：无
     * 返回值说明：无
     */
    updateFloatingBar() {
        const checkedCount = document.querySelectorAll('.file-checkbox:checked').length;
        const { floatingBar, globalDeleteBtn } = this.elements;
        if (checkedCount > 0) {
            floatingBar.style.display = 'flex';
            globalDeleteBtn.textContent = `删除选中的 ${checkedCount} 个文件`;
        } else {
            floatingBar.style.display = 'none';
        }
    }
};

// --- API 交互模块 ---
const DuplicateCheckAPI = {
    /**
     * 用途说明：向后端发送请求开始查重任务
     * 入参说明：无
     * 返回值说明：无
     */
    async start() {
        try {
            const response = await Request.post('/api/file_repository/duplicate/check', {}, {}, true);
            if (response.status === 'success') {
                Toast.show('查重任务已启动');
                CheckState.results = [];
                UIController.toggleView('checking');
                App.startPolling();
            } else {
                Toast.show(response.message);
            }
        } catch (error) {
            Toast.show('启动失败');
        }
    },

    /**
     * 用途说明：向后端发送请求停止正在进行的查重任务
     * 入参说明：无
     * 返回值说明：无
     */
    async stop() {
        if (!confirm('确定要终止当前的查重任务吗？')) return;
        try {
            const response = await Request.post('/api/file_repository/duplicate/stop', {}, {}, true);
            if (response.status === 'success') {
                Toast.show('正在停止任务...');
            }
        } catch (error) {
            Toast.show('请求停止失败');
        }
    },

    /**
     * 用途说明：向后端轮询查重任务的最新进度和结果
     * 入参说明：无
     * 返回值说明：Object - 后端返回的数据对象
     */
    async fetchProgress() {
        try {
            const response = await Request.get('/api/file_repository/duplicate/progress', {}, false);
            if (response.status === 'success') {
                return response.data;
            }
        } catch (error) {
            console.error('获取查重进度失败:', error);
        }
        return null;
    },

    /**
     * 用途说明：向后端发送请求删除指定的物理文件
     * 入参说明：path (String) - 文件绝对路径
     * 返回值说明：Object - 请求响应结果
     */
    async deleteFile(path) {
        return await Request.post('/api/file_repository/duplicate/delete', { file_path: path }, {}, true);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：应用初始化，设置 UI 并检查初始任务状态
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        
        // 绑定底部批量删除按钮逻辑
        if (UIController.elements.globalDeleteBtn) {
            UIController.elements.globalDeleteBtn.onclick = () => this.handleBatchDelete();
        }

        // 检查页面进入时的初始状态
        this.checkInitialStatus();
    },

    /**
     * 用途说明：首次进入页面时获取一次任务状态
     * 入参说明：无
     * 返回值说明：无
     */
    async checkInitialStatus() {
        const data = await DuplicateCheckAPI.fetchProgress();
        if (data) {
            this.processStatusUpdate(data);
        }
    },

    /**
     * 用途说明：启动定时轮询
     * 入参说明：无
     * 返回值说明：无
     */
    startPolling() {
        if (CheckState.pollingInterval) return;
        CheckState.pollingInterval = setInterval(async () => {
            const data = await DuplicateCheckAPI.fetchProgress();
            if (data) {
                this.processStatusUpdate(data);
            }
        }, 1000);
    },

    /**
     * 用途说明：停止定时轮询
     * 入参说明：无
     * 返回值说明：无
     */
    stopPolling() {
        if (CheckState.pollingInterval) {
            clearInterval(CheckState.pollingInterval);
            CheckState.pollingInterval = null;
        }
    },

    /**
     * 用途说明：处理 API 返回的状态和数据更新 UI
     * 入参说明：data (Object) - 包含 status, progress, results 的数据包
     * 返回值说明：无
     */
    processStatusUpdate(data) {
        const { status, progress, results } = data;
        
        if (status === 'checking') {
            this.startPolling();
            UIController.toggleView('checking');
            UIController.updateProgress(progress);
        } else {
            this.stopPolling();
            
            // 查重已完成或空闲状态时的逻辑
            if (status === 'completed' && results !== undefined) {
                CheckState.setResults(results);
                UIController.renderResults();
            }
            
            // 更新视图显示状态
            UIController.toggleView(status);
        }
    },

    /**
     * 用途说明：处理选中的重复文件批量删除逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    async handleBatchDelete() {
        const checkedBoxes = document.querySelectorAll('.file-checkbox:checked');
        if (checkedBoxes.length === 0) return;

        if (!confirm(`确定要删除选中的 ${checkedBoxes.length} 个文件吗？此操作不可撤销！`)) return;

        const paths = Array.from(checkedBoxes).map(cb => cb.getAttribute('data-path'));
        let successCount = 0;

        // 串行执行删除，保证前端状态更新的准确性
        for (const path of paths) {
            try {
                const response = await DuplicateCheckAPI.deleteFile(path);
                if (response.status === 'success') {
                    successCount++;
                    this.removeFileFromState(path);
                }
            } catch (error) {
                console.error('删除文件失败:', path, error);
            }
        }

        if (successCount > 0) {
            Toast.show(`成功删除 ${successCount} 个文件`);
            UIController.renderResults();
        } else {
            Toast.show('删除操作未成功');
        }
    },

    /**
     * 用途说明：在前端内存中移除已删除的文件，并自动过滤掉空分组
     * 入参说明：path (String) - 已删除的文件路径
     * 返回值说明：无
     */
    removeFileFromState(path) {
        CheckState.results = CheckState.results.map(group => {
            const newFiles = group.files.filter(f => f.file_path !== path);
            return { ...group, files: newFiles };
        }).filter(group => group.files.length > 0);
    }
};

// 页面加载完成后启动应用
document.addEventListener('DOMContentLoaded', () => App.init());
