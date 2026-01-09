/**
 * 用途说明：查重页面 logic 处理，负责触发查重任务、进度监控以及查重结果的分页展示与交互。
 */

// --- 状态管理 ---
const CheckState = {
    results: [],
    page: 1,
    limit: 100,
    total: 0,
    lastCheckTime: '--',
    pollingInterval: null,
    settings: null, // 存储系统设置
    paginationController: null, // 分页控制器实例
    previousExpandedStates: null, // 用途说明：存储上一页结果的展开/收起状态，用于刷新后保留状态

    /**
     * 用途说明：更新结果列表及分页信息
     * 入参说明：data (Object) - 后端返回的 PaginationResult 结构
     * 入参说明：expandedStatesMap (Object|null) - 存储分组ID到isExpanded状态的映射，用于恢复分组的展开状态
     * 返回值说明：无
     */
    setPaginationData(data, expandedStatesMap = null) {
        this.results = data.list || [];
        this.total = data.total || 0;
        this.page = data.page || 1;
        this.limit = data.limit || 100;

        // 恢复分组的展开状态
        this.results.forEach(group => {
            if (expandedStatesMap && expandedStatesMap[group.id] !== undefined) {
                group.isExpanded = expandedStatesMap[group.id];
            } else {
                // 默认为展开状态
                group.isExpanded = true;
            }
        });

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
        
        // 初始化公用分页组件
        CheckState.paginationController = UIComponents.initPagination('pagination-container', {
            limit: CheckState.limit,
            onPageChange: (newPage) => App.changePage(newPage)
        });

        // 绑定全局删除按钮
        this.elements.globalDeleteBtn.onclick = () => {
            const checkedCbs = document.querySelectorAll('.file-checkbox:checked');
            const paths = Array.from(checkedCbs).map(cb => cb.getAttribute('data-path'));
            if (paths.length > 0) {
                App.deleteFiles(paths, `确定要删除选中的 ${paths.length} 个文件吗？\n(删除后若组内文件少于2个，该组将自动解散)`);
            }
        };

        this.renderHeader(ProgressStatus.IDLE);
    },

    /**
     * 用途说明：渲染顶部导航栏，根据任务状态切换“开始”与“停止”按钮
     * 入参说明：status (String) - ProgressStatus 枚举值
     * 返回值说明：无
     */
    renderHeader(status) {
        if (typeof UIComponents !== 'undefined') {
            const title = '文件查重';
            if (status === ProgressStatus.PROCESSING) {
                UIComponents.initHeader(title, true, null, '停止查重', () => DuplicateCheckAPI.stop(), 'btn-text-danger');
            } else {
                UIComponents.initHeader(title, true, null, '开始查重', () => DuplicateCheckAPI.start());
            }
        }
    },

    /**
     * 用途说明：切换页面视图状态（查重中、显示结果、显示初始引导）
     * 入参说明：status (String) - 任务状态（ProgressStatus 枚举值）
     * 返回值说明：无
     */
    toggleView(status) {
        const { scanningContainer, resultsGroup, emptyHint } = this.elements;
        if (status === ProgressStatus.PROCESSING) {
            this.renderHeader(ProgressStatus.PROCESSING);
            scanningContainer.style.display = 'flex';
            resultsGroup.style.display = 'none';
            emptyHint.style.display = 'none';
            UIComponents.showProgressBar('#scanning-container', '正在准备分析文件...');
        } else {
            this.renderHeader(ProgressStatus.IDLE);
            scanningContainer.style.display = 'none';
            UIComponents.hideProgressBar('#scanning-container');

            if (status === ProgressStatus.COMPLETED || (CheckState.results && CheckState.results.length > 0)) {
                resultsGroup.style.display = 'flex';
                emptyHint.style.display = 'none';
            } else {
                resultsGroup.style.display = 'none';
                emptyHint.style.display = (status === ProgressStatus.IDLE) ? 'block' : 'none';
            }
        }
    },

    /**
     * 用途说明：更新扫描进度条和状态文字
     * 入参说明：progress (Object) - 进度数据
     * 返回值说明：无
     */
    updateProgress(progress) {
        UIComponents.renderProgress('#scanning-container', progress);
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
        if (!results || results.length === 0) {
            summaryBar.style.display = 'none';
            wrapper.innerHTML = '<div style="text-align: center; color: #9aa0a6; padding-top: 100px;">未发现重复文件</div>';
            if (CheckState.paginationController) CheckState.paginationController.update(0, 1);
            this.updateFloatingBar();
            return;
        }

        summaryBar.style.display = 'block';
        summaryGroups.textContent = `重复组总数: ${CheckState.total}`;
        const totalFiles = results.reduce((acc, g) => acc + (g.file_ids ? g.file_ids.length : 0), 0);
        summaryFiles.textContent = `当前页文件: ${totalFiles}`;
        summaryTime.textContent = `刷新时间: ${CheckState.lastCheckTime}`;

        results.forEach(group => {
            const groupEl = this.createGroupElement(group);
            wrapper.appendChild(groupEl);
        });

        // 更新公用分页组件
        if (CheckState.paginationController) {
            CheckState.paginationController.update(CheckState.total, CheckState.page);
        }

        this.updateFloatingBar();
    },

    /**
     * 用途说明：创建一个重复分组的 DOM 元素
     * 入参说明：group (Object) - 分组数据 (DuplicateGroupResult)
     * 返回值说明：HTMLElement - 分组节点
     */
    createGroupElement(group) {
        const groupEl = document.createElement('div');
        groupEl.className = `duplicate-group ${group.isExpanded ? 'expanded' : ''}`;
        groupEl.setAttribute('data-group-id', group.id);

        const files = group.file_ids || [];
        const fileCount = files.length;
        const groupType = group.group_name || '重复组';

        groupEl.innerHTML = `
            <div class="group-header">
                <div class="group-info">
                    <span class="group-title">${groupType}</span>
                    <span class="group-count">${fileCount} 个文件</span>
                    <span class="group-md5">ID: ${group.id}</span>
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
                        ${files.map(f => {
                            const fileName = f.file_path.split(/[\/]/).pop();
                            return `
                                <tr class="clickable-row" data-thumbnail="${f.thumbnail_path || ''}">
                                    <td style="width: 25%;" title="${fileName}">${fileName}</td>
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

        const header = groupEl.querySelector('.group-header');

        header.addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            groupEl.classList.toggle('expanded');
            // 用途说明：更新状态管理中的分组展开状态
            const groupId = groupEl.getAttribute('data-group-id');
            const targetGroup = CheckState.results.find(g => String(g.id) === groupId);
            if (targetGroup) {
                targetGroup.isExpanded = groupEl.classList.contains('expanded');
            }
        });

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

        groupEl.querySelectorAll('.clickable-row').forEach(tr => {
            tr.addEventListener('click', (e) => {
                const cb = tr.querySelector('.file-checkbox');
                if (e.target !== cb) {
                    cb.checked = !cb.checked;
                    // 手动触发 change 事件或直接调用逻辑
                    if (cb.checked) tr.classList.add('selected-row');
                    else tr.classList.remove('selected-row');
                    if (!cb.checked) selectAllCheckbox.checked = false;
                    this.updateFloatingBar();
                }
            });

            const checkbox = tr.querySelector('.file-checkbox');
            checkbox.onclick = (e) => {
                e.stopPropagation();
                if (checkbox.checked) tr.classList.add('selected-row');
                else tr.classList.remove('selected-row');
                if (!checkbox.checked) selectAllCheckbox.checked = false;
                this.updateFloatingBar();
            };

            if (CheckState.settings && CheckState.settings.file_repository.quick_view_thumbnail) {
                tr.addEventListener('mouseenter', (e) => UIComponents.showQuickPreview(e, tr.getAttribute('data-thumbnail')));
                tr.addEventListener('mousemove', (e) => UIComponents.moveQuickPreview(e));
                tr.addEventListener('mouseleave', () => UIComponents.hideQuickPreview());
            }
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
                UIController.toggleView(ProgressStatus.PROCESSING);
                App.startPolling();
            } else {
                Toast.show(response.message);
            }
        } catch (error) {
            Toast.show('启动失败');
        }
    },

    /**
     * 用途说明：向后端发送请求停止查重任务
     * 入参说明：无
     * 返回值说明：无
     */
    async stop() {
        if (!confirm('确定要终止当前的查重任务吗？')) return;
        try {
            const response = await Request.post('/api/file_repository/duplicate/stop', {}, {}, true);
            if (response.status === 'success') Toast.show('正在停止任务...');
        } catch (error) {
            Toast.show('请求停止失败');
        }
    },

    /**
     * 用途说明：向后端轮询查重任务的最新进度
     * 入参说明：无
     * 返回值说明：Object - 包含 status 和 progress
     */
    async fetchProgress() {
        try {
            const response = await Request.get('/api/file_repository/duplicate/progress', {}, false);
            if (response.status === 'success') return response.data;
        } catch (error) {
            console.error('获取查重进度失败:', error);
        }
        return null;
    },

    /**
     * 用途说明：分页获取查重结果数据
     * 入参说明：page (int), limit (int)
     * 返回值说明：Object - PaginationResult
     */
    async fetchList(page, limit) {
        try {
            const response = await Request.get('/api/file_repository/duplicate/list', { page, limit }, false);
            if (response.status === 'success') return response.data;
        } catch (error) {
            console.error('获取结果列表失败:', error);
        }
        return null;
    },

    /**
     * 用途说明：调用通用删除 API 批量删除文件
     * 入参说明：paths (Array) - 文件路径列表
     * 返回值说明：Object - 后端响应结果
     */
    async deleteFiles(paths) {
        try {
            return await Request.post('/api/file_repository/delete', { file_paths: paths }, {}, true);
        } catch (error) {
            console.error('删除文件请求失败:', error);
            return { status: 'error', message: '请求失败' };
        }
    }
};

// --- 应用入口 ---
const App = {
    /**
     * 用途说明：应用启动入口
     * 入参说明：无
     * 返回值说明：无
     */
    async init() {
        UIController.init();

        // 获取系统配置
        try {
            const configResp = await Request.get('/api/setting/get');
            if (configResp.status === 'success') CheckState.settings = configResp.data;
        } catch (e) {}

        // 初始化时检查一次进度
        const data = await DuplicateCheckAPI.fetchProgress();
        if (data) {
            if (data.status === ProgressStatus.PROCESSING) {
                UIController.toggleView(ProgressStatus.PROCESSING);
                this.startPolling();
            } else if (data.status === ProgressStatus.COMPLETED) {
                // 用途说明：初次加载或任务完成时，无需恢复展开状态
                this.loadResults(1);
            } else {
                UIController.toggleView(ProgressStatus.IDLE);
            }
        }
    },

    /**
     * 用途说明：加载指定页码的结果数据
     * 入参说明：page (int) - 目标页码
     * 返回值说明：无
     */
    async loadResults(page) {
        const data = await DuplicateCheckAPI.fetchList(page, CheckState.limit);
        if (data) {
            // 用途说明：传递之前缓存的展开状态，并在处理后清除
            CheckState.setPaginationData(data, CheckState.previousExpandedStates);
            CheckState.previousExpandedStates = null; // 清除缓存的状态
            UIController.toggleView(ProgressStatus.COMPLETED);
            UIController.renderResults();
        }
    },

    /**
     * 用途说明：切换页码逻辑
     * 入参说明：page (int)
     * 返回值说明：无
     */
    async changePage(page) {
        if (page < 1) return;
        // 用途说明：页面切换时，记录当前所有分组的展开状态
        const expandedStatesMap = {};
        CheckState.results.forEach(group => {
            expandedStatesMap[group.id] = group.isExpanded;
        });
        CheckState.previousExpandedStates = expandedStatesMap; // 缓存状态
        await this.loadResults(page);
        window.scrollTo(0, 0);
    },

    /**
     * 用途说明：批量删除文件并刷新列表
     * 入参说明：paths (Array) - 路径列表, confirmMsg (String) - 确认提示词
     * 返回值说明：无
     */
    async deleteFiles(paths, confirmMsg) {
        if (!paths || paths.length === 0) return;

        UIComponents.showConfirmModal({
            message: confirmMsg,
            confirmText: '确定删除',
            onConfirm: async () => {
                const response = await DuplicateCheckAPI.deleteFiles(paths);
                if (response.status === 'success') {
                    Toast.show(response.message || '删除成功');
                    // 用途说明：在刷新结果前，保存当前页所有分组的展开状态
                    const expandedStatesMap = {};
                    CheckState.results.forEach(group => {
                        expandedStatesMap[group.id] = group.isExpanded;
                    });
                    CheckState.previousExpandedStates = expandedStatesMap; // 缓存状态
                    this.loadResults(CheckState.page);
                } else {
                    Toast.show(response.message || '删除失败');
                }
            }
        });
    },

    /**
     * 用途说明：开启定时轮询任务状态
     * 入参说明：无
     * 返回值说明：无
     */
    startPolling() {
        if (CheckState.pollingInterval) return;
        CheckState.pollingInterval = setInterval(async () => {
            const data = await DuplicateCheckAPI.fetchProgress();
            if (!data) return;

            if (data.status === ProgressStatus.PROCESSING) {
                UIController.updateProgress(data.progress);
            } else {
                this.stopPolling();
                if (data.status === ProgressStatus.COMPLETED) {
                    Toast.show('查重已完成');
                    // 用途说明：任务完成后，无需恢复展开状态
                    this.loadResults(1);
                } else {
                    UIController.toggleView(data.status);
                }
            }
        }, 1500);
    },

    /**
     * 用途说明：停止轮询
     * 入参说明：无
     * 返回值说明：无
     */
    stopPolling() {
        if (CheckState.pollingInterval) {
            clearInterval(CheckState.pollingInterval);
            CheckState.pollingInterval = null;
        }
    }
};

// 页面加载完成后启动
document.addEventListener('DOMContentLoaded', () => App.init());