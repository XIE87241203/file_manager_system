/**
 * 用途说明：回收站页面逻辑处理，负责已删除文件的展示、彻底删除、恢复及分页搜索。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 20,
    sortBy: 'recycle_bin_time',
    order: 'DESC',
    search: '',
    selectedPaths: new Set(),
    paginationController: null,
    lastTaskStatus: null // 用途说明：缓存上一次任务状态，用于判断状态切换
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用公用组件初始化顶部栏
        UIComponents.initRepoHeader({
            searchPlaceholder: '搜索文件名 (正则模糊匹配)...',
            showHistoryCheckbox: false,
            onSearch: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('file-list-body'),
            searchInput: document.getElementById('search-input'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            clearRecycleBtn: document.getElementById('btn-clear-recycle-bin'),
            restoreSelectedBtn: document.getElementById('btn-restore-selected'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

        // 初始化分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadFileList();
                window.scrollTo(0, 0);
            }
        });

        // 绑定表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedPaths,
            onSelectionChange: () => this.updateActionButtons()
        });
    },

    /**
     * 用途说明：渲染表格内容
     * 入参说明：list: 文件对象列表
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        if (!list || list.length === 0) {
            // 用途说明：动态调整空状态的列跨度，包含新增的文件类型、时长、编码列
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(8, '回收站空空如也');
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            if (isChecked) tr.classList.add('selected-row');

            // 用途说明：文件名直接从 API 返回的 file_name 字段获取
            const fileName = file.file_name || '未知文件名';
            const fileSizeStr = CommonUtils.formatFileSize(file.file_size);
            // 用途说明：使用 CommonUtils.formatDuration 格式化视频时长
            const durationStr = CommonUtils.formatDuration(file.video_duration);

            tr.innerHTML = `
                <td class="col-name" title="${fileName}">${fileName}</td>
                <td class="col-size">${fileSizeStr}</td>
                <td class="col-path" title="${file.file_path}">${file.file_path}</td>
                <td class="col-type">${file.file_type || '未知'}</td>
                <td class="col-duration">${durationStr}</td>
                <td class="col-codec">${file.video_codec || 'N/A'}</td>
                <td class="col-time">${file.recycle_bin_time}</td>
                <td class="col-check">
                    <input type="checkbox" class="file-checkbox" data-path="${file.file_path}" ${isChecked ? 'checked' : ''}>
                </td>
            `;
            tableBody.appendChild(tr);
        });
        
        this.updateActionButtons();
    },

    /**
     * 用途说明：更新排序 UI 样式
     * 入参说明：field: 排序字段, order: 排序方向 (ASC/DESC)
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：根据选中状态更新操作按钮（恢复/彻底删除）的显示
     * 入参说明：无
     * 返回值说明：无
     */
    updateActionButtons() {
        const { restoreSelectedBtn, deleteSelectedBtn, clearRecycleBtn } = this.elements;
        const count = State.selectedPaths.size;

        if (count > 0) {
            restoreSelectedBtn.classList.remove('hidden');
            restoreSelectedBtn.textContent = `恢复选中 (${count})`;
            deleteSelectedBtn.classList.remove('hidden');
            deleteSelectedBtn.textContent = `彻底删除 (${count})`;
            clearRecycleBtn.classList.add('hidden');
        } else {
            restoreSelectedBtn.classList.add('hidden');
            deleteSelectedBtn.classList.add('hidden');
            clearRecycleBtn.classList.remove('hidden');
        }
    }
};

// --- API 交互模块 ---
const RecycleBinAPI = {
    /**
     * 用途说明：分页获取回收站文件列表
     * 入参说明：params: 包含 page, limit, sort_by, order_asc, search 等参数的对象
     * 返回值说明：返回 API 响应结果，包含文件列表和分页信息
     */
    async getList(params) {
        const query = new URLSearchParams(params).toString();
        // 修改说明：API 路径调整为后端最新的专有回收站列表路由
        return await Request.get('/api/file_repository/recycle_bin/list?' + query);
    },

    /**
     * 用途说明：从回收站恢复文件
     * 入参说明：filePaths: 要恢复的文件路径数组
     * 返回值说明：返回 API 响应结果
     */
    async restoreFiles(filePaths) {
        return await Request.post('/api/file_repository/restore_from_recycle_bin', { file_paths: filePaths });
    },

    /**
     * 用途说明：批量彻底删除回收站中的文件
     * 入参说明：filePaths: 要彻底删除的文件路径数组
     * 返回值说明：返回 API 响应结果
     */
    async deleteFiles(filePaths) {
        // 彻底删除进度条开启时，禁用默认 mask
        return await Request.post('/api/file_repository/clear_recycle_bin', { file_paths: filePaths }, {}, false);
    },

    /**
     * 用途说明：清空整个回收站
     * 入参说明：无
     * 返回值说明：返回 API 响应结果
     */
    async clearAll() {
        // 清空进度条开启时，禁用默认 mask
        return await Request.post('/api/file_repository/clear_recycle_bin', {}, {}, false);
    },

    /**
     * 用途说明：获取清理回收站任务的执行进度
     * 入参说明：无
     * 返回值说明：返回 API 响应结果，包含进度和状态
     */
    async getDeleteProgress() {
        // 轮询进度时一律不显示 mask，防止页面抖动
        return await Request.get('/api/file_repository/clear_recycle_bin/progress', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：页面初始化
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadFileList();
        this.checkTaskStatus();
    },

    /**
     * 用途说明：绑定页面交互事件
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { clearRecycleBtn, restoreSelectedBtn, deleteSelectedBtn, sortableHeaders } = UIController.elements;

        if (clearRecycleBtn) clearRecycleBtn.onclick = () => this.handleClearAll();
        if (restoreSelectedBtn) restoreSelectedBtn.onclick = () => this.handleRestore();
        if (deleteSelectedBtn) deleteSelectedBtn.onclick = () => this.handleDeleteSelected();

        sortableHeaders.forEach(th => {
            th.onclick = () => {
                const field = th.getAttribute('data-field');
                if (State.sortBy === field) {
                    State.order = State.order === 'ASC' ? 'DESC' : 'ASC';
                } else {
                    State.sortBy = field;
                    State.order = 'DESC';
                }
                UIController.updateSortUI(State.sortBy, State.order);
                this.loadFileList();
            };
        });
    },

    /**
     * 用途说明：处理搜索逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleSearch() {
        const { searchInput } = UIController.elements;
        State.search = searchInput.value.trim();
        State.page = 1;
        State.selectedPaths.clear();
        this.loadFileList();
    },

    /**
     * 用途说明：加载回收站文件列表数据并触发渲染
     * 入参说明：无
     * 返回值说明：无
     */
    async loadFileList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };
        const res = await RecycleBinAPI.getList(params);
        if (res.status === 'success') {
            UIController.renderTable(res.data.list);
            State.paginationController.update(res.data.total, res.data.page);
        }
    },

    /**
     * 用途说明：处理恢复选中文件逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    async handleRestore() {
        const paths = Array.from(State.selectedPaths);
        UIComponents.showConfirmModal({
            title: '恢复文件',
            message: `确定要将选中的 ${paths.length} 个文件恢复到仓库吗？`,
            confirmText: '确定恢复',
            onConfirm: async () => {
                const res = await RecycleBinAPI.restoreFiles(paths);
                if (res.status === 'success') {
                    Toast.show('已恢复');
                    State.selectedPaths.clear();
                    this.loadFileList();
                }
            }
        });
    },

    /**
     * 用途说明：处理彻底删除选中文件逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    async handleDeleteSelected() {
        const paths = Array.from(State.selectedPaths);
        UIComponents.showConfirmModal({
            title: '彻底删除',
            message: `确定要彻底删除选中的 ${paths.length} 个文件吗？此操作不可恢复，将物理删除磁盘文件！`,
            confirmText: '确定删除',
            onConfirm: async () => {
                const res = await RecycleBinAPI.deleteFiles(paths);
                if (res.status === 'success') {
                    Toast.show('删除任务已启动');
                    this.startProgressPolling();
                }
            }
        });
    },

    /**
     * 用途说明：处理清空回收站逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    async handleClearAll() {
        UIComponents.showConfirmModal({
            title: '清空回收站',
            message: '确定要清空回收站中所有的文件吗？这将物理删除所有回收站内的磁盘文件！',
            confirmText: '确定清空',
            onConfirm: async () => {
                const res = await RecycleBinAPI.clearAll();
                if (res.status === 'success') {
                    Toast.show('清空任务已启动');
                    this.startProgressPolling();
                }
            }
        });
    },

    /**
     * 用途说明：启动进度轮询，并根据状态切换逻辑决定是否刷新列表。
     * 入参说明：无
     * 返回值说明：无
     */
    startProgressPolling() {
        UIComponents.showProgressBar('.repo-container', '正在删除文件...');
        // 初始化当前状态，确保能识别后续的 IDLE 切换
        State.lastTaskStatus = ProgressStatus.PROCESSING;

        const timer = setInterval(async () => {
            const res = await RecycleBinAPI.getDeleteProgress();
            if (res.status === 'success') {
                const currentStatus = res.data.status;
                const progress = res.data.progress;

                if (currentStatus === ProgressStatus.PROCESSING) {
                    UIComponents.renderProgress('.repo-container', progress);
                } else {
                    // 状态不再是 PROCESSING，停止轮询
                    clearInterval(timer);
                    UIComponents.hideProgressBar('.repo-container');

                    // 核心逻辑：如果从 PROCESSING 切换到 IDLE，或者变为 COMPLETED，则刷新
                    const isTaskFinished = (State.lastTaskStatus === ProgressStatus.PROCESSING && currentStatus === ProgressStatus.IDLE)
                                         || currentStatus === ProgressStatus.COMPLETED;

                    if (isTaskFinished) {
                        Toast.show('处理完成');
                        State.selectedPaths.clear();
                        this.loadFileList();
                    }
                }
                // 更新缓存状态
                State.lastTaskStatus = currentStatus;
            } else {
                clearInterval(timer);
                UIComponents.hideProgressBar('.repo-container');
                State.lastTaskStatus = null;
            }
        }, 1000);
    },

    /**
     * 用途说明：进入页面时检查是否有正在进行的删除任务
     * 入参说明：无
     * 返回值说明：无
     */
    async checkTaskStatus() {
        const res = await RecycleBinAPI.getDeleteProgress();
        if (res.status === 'success' && res.data.status === ProgressStatus.PROCESSING) {
            this.startProgressPolling();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
