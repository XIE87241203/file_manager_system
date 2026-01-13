/**
 * 用途说明：回收站页面逻辑处理，负责已标记删除的文件列表展示、分页、排序、搜索及彻底删除、恢复、一键清空操作。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 20,
    sortBy: 'recycle_bin_time', // 默认按回收时间排序
    order: 'DESC',
    search: '',
    selectedPaths: new Set(), // 存储选中文件的路径
    settings: null, // 存储系统设置
    paginationController: null, // 分页控制器实例
    clearInterval: null, // 清空/删除任务进度的定时器
    isProcessing: false // 标记前端是否认为当前处于处理流程中
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
            tableBody: document.getElementById('file-list-body'),
            mainContent: document.getElementById('repo-main-content'),
            searchInput: document.getElementById('search-input'),
            backBtn: document.getElementById('nav-back-btn'),
            searchBtn: document.getElementById('search-btn'),
            sortableHeaders: document.querySelectorAll('th.sortable'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            restoreSelectedBtn: document.getElementById('btn-restore-selected'),
            btnClearRecycleBin: document.getElementById('btn-clear-recycle-bin')
        };
        // 初始化公用分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadFileList();
                window.scrollTo(0, 0);
            }
        });
        
        // 绑定通用表格选中逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedPaths,
            onSelectionChange: () => this.updateActionButtonsVisibility()
        });

        // 动态避开头部高度
        const repoContainer = document.querySelector('.repo-container');
        if (repoContainer) {
            repoContainer.style.marginTop = UIComponents.getToolbarHeight() + 'px';
        }
    },

    /**
     * 用途说明：渲染文件表格内容
     * 入参说明：list: Array - 包含文件信息的对象列表
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox, btnClearRecycleBin } = this.elements;
        tableBody.innerHTML = '';
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }

        // 无论列表是否为空，都更新一次选中操作按钮状态
        this.updateActionButtonsVisibility();

        // 处理“清空回收站”按钮的可见性：列表为空时隐藏，有内容且非搜索状态下显示
        if (btnClearRecycleBin) {
            if (!list || list.length === 0) {
                btnClearRecycleBin.classList.add('hidden');
            } else {
                btnClearRecycleBin.classList.remove('hidden');
            }
        }

        if (!list || list.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 100px; color: #9aa0a6;">回收站空空如也</td></tr>`;
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            if (isChecked) tr.classList.add('selected-row');
            
            const fileName = UIComponents.getFileName(file.file_path);
            
            tr.innerHTML = `
                <td title="${fileName}">${fileName}</td>
                <td title="${file.file_path}">${file.file_path}</td>
                <td><code>${file.file_md5}</code></td>
                <td>${file.recycle_bin_time || '未知'}</td>
                <td style="text-align: center;">
                    <input type="checkbox" class="file-checkbox" data-path="${file.file_path}" ${isChecked ? 'checked' : ''}>
                </td>
            `;

            tableBody.appendChild(tr);
        });
    },

    /**
     * 用途说明：更新分页控件显示状态
     * 入参说明：total: Number - 总条数, page: Number - 当前页码
     * 返回值说明：无
     */
    updatePagination(total, page) {
        if (State.paginationController) {
            State.paginationController.update(total, page);
        }
    },

    /**
     * 用途说明：更新表头排序图标和样式
     * 入参说明：field: String - 排序字段, order: String - 'ASC' 或 'DESC'
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：根据选中状态更新操作按钮（删除、恢复）可见性
     * 入参说明：无
     * 返回值说明：无
     */
    updateActionButtonsVisibility() {
        const { deleteSelectedBtn, restoreSelectedBtn } = this.elements;
        const count = State.selectedPaths.size;
        
        if (count > 0) {
            if (deleteSelectedBtn) {
                deleteSelectedBtn.classList.remove('hidden');
                deleteSelectedBtn.textContent = `彻底删除选中 (${count})`;
            }
            if (restoreSelectedBtn) {
                restoreSelectedBtn.classList.remove('hidden');
                restoreSelectedBtn.textContent = `移出回收站 (${count})`;
            }
        } else {
            if (deleteSelectedBtn) deleteSelectedBtn.classList.add('hidden');
            if (restoreSelectedBtn) restoreSelectedBtn.classList.add('hidden');
        }
    },

    /**
     * 用途说明：切换正在执行删除/清空任务时的 UI 显示
     * 入参说明：isProcessing: Boolean - 是否正在处理, message: String - 初始提示语
     * 返回值说明：无
     */
    toggleProcessingUI(isProcessing, message = '正在准备任务...') {
        const { mainContent, btnClearRecycleBin, deleteSelectedBtn, restoreSelectedBtn } = this.elements;
        if (isProcessing) {
            if (mainContent) mainContent.style.visibility = 'hidden';
            if (btnClearRecycleBin) {
                btnClearRecycleBin.disabled = true;
                btnClearRecycleBin.classList.add('is-processing');
            }
            if (deleteSelectedBtn) deleteSelectedBtn.disabled = true;
            if (restoreSelectedBtn) restoreSelectedBtn.disabled = true;
            
            UIComponents.showProgressBar('.repo-container', message);
        } else {
            if (mainContent) mainContent.style.visibility = 'visible';
            if (btnClearRecycleBin) {
                btnClearRecycleBin.disabled = false;
                btnClearRecycleBin.classList.remove('is-processing');
            }
            if (deleteSelectedBtn) deleteSelectedBtn.disabled = false;
            if (restoreSelectedBtn) restoreSelectedBtn.disabled = false;
            
            UIComponents.hideProgressBar('.repo-container');
        }
    },

    /**
     * 用途说明：更新进度条内容
     * 入参说明：progress: Object - 进度数据
     * 返回值说明：无
     */
    updateProgress(progress) {
        UIComponents.renderProgress('.repo-container', progress);
    }
};

// --- API 交互模块 ---
const RecycleBinAPI = {
    /**
     * 用途说明：获取回收站文件列表
     * 入参说明：params: Object - 包含 page, limit, sort_by, order_asc, search 等参数
     * 返回值说明：Promise - 解析为后端返回的 JSON 数据
     */
    async getFileList(params) {
        params.is_in_recycle_bin = true;
        const query = new URLSearchParams(params).toString();
        return await Request.get(`/api/file_repository/list?${query}`, {}, true);
    },

    /**
     * 用途说明：批量彻底删除指定文件（调用新的异步接口）
     * 入参说明：filePaths: Array - 文件完整路径列表
     * 返回值说明：Promise - 解析为操作结果状态
     */
    async deleteFiles(filePaths) {
        return await Request.post('/api/file_repository/clear_recycle_bin', { file_paths: filePaths }, {}, true);
    },

    /**
     * 用途说明：批量将文件移出回收站
     * 入参说明：filePaths: Array - 文件完整路径列表
     * 返回值说明：Promise - 解析为操作结果状态
     */
    async restoreFiles(filePaths) {
        return await Request.post('/api/file_repository/restore_from_recycle_bin', { file_paths: filePaths }, {}, true);
    },

    /**
     * 用途说明：发起全量清空回收站任务
     * 入参说明：无
     * 返回值说明：Promise - 解析为后端返回的 JSON 数据
     */
    async clearRecycleBin() {
        return await Request.post('/api/file_repository/clear_recycle_bin', {}, {}, true);
    },

    /**
     * 用途说明：获取当前异步任务（删除或清空）的进度
     * 入参说明：无
     * 返回值说明：Promise - 解析为后端返回的 JSON 数据
     */
    async getTaskProgress() {
        return await Request.get('/api/file_repository/clear_recycle_bin/progress', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用入口
     * 入参说明：无
     * 返回值说明：无
     */
    async init() {
        UIController.init();
        this.bindEvents();
        this.loadFileList();
        this.checkTaskStatus(); // 初始化时检查是否有正在进行的任务
    },

    /**
     * 用途说明：绑定页面交互事件
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { 
            searchInput, searchBtn, sortableHeaders,
            deleteSelectedBtn, restoreSelectedBtn, backBtn,
            btnClearRecycleBin
        } = UIController.elements;

        if (backBtn) {
            backBtn.onclick = () => window.history.back();
        }

        const onSearch = () => {
            State.search = searchInput.value.trim();
            State.page = 1;
            State.selectedPaths.clear(); 
            this.loadFileList();
        };
        if (searchBtn) searchBtn.onclick = onSearch;
        if (searchInput) searchInput.onkeypress = (e) => { if (e.key === 'Enter') onSearch(); };

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

        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleDeleteSelected();
        }

        if (restoreSelectedBtn) {
            restoreSelectedBtn.onclick = () => this.handleRestoreSelected();
        }

        if (btnClearRecycleBin) {
            btnClearRecycleBin.onclick = () => this.handleClearRecycleBin();
        }
    },

    /**
     * 用途说明：从服务端加载并渲染文件列表
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

        const response = await RecycleBinAPI.getFileList(params);
        if (response.status === 'success') {
            const data = response.data;
            UIController.renderTable(data.list);
            UIController.updatePagination(data.total, data.page);
        } else {
            Toast.show(response.message);
        }
    },

    /**
     * 用途说明：处理批量删除选中文件的逻辑，发起异步任务并展示进度
     * 入参说明：无
     * 返回值说明：无
     */
    async handleDeleteSelected() {
        if (State.selectedPaths.size === 0) return;
        
        UIComponents.showConfirmModal({
            title: '彻底删除',
            message: `确定要永久删除选中的 ${State.selectedPaths.size} 个文件吗？此操作无法撤销！`,
            confirmText: '彻底删除',
            onConfirm: async () => {
                const response = await RecycleBinAPI.deleteFiles(Array.from(State.selectedPaths));
                if (response.status === 'success') {
                    Toast.show('已启动批量删除任务');
                    State.selectedPaths.clear();
                    State.isProcessing = true; 
                    this.checkTaskStatus();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

    /**
     * 用途说明：处理恢复选中文件的逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    async handleRestoreSelected() {
        if (State.selectedPaths.size === 0) return;

        UIComponents.showConfirmModal({
            title: '恢复文件',
            message: `确定要将选中的 ${State.selectedPaths.size} 个文件恢复到仓库吗？`,
            confirmText: '立即恢复',
            onConfirm: async () => {
                const response = await RecycleBinAPI.restoreFiles(Array.from(State.selectedPaths));
                if (response.status === 'success') {
                    Toast.show('文件已成功恢复');
                    State.selectedPaths.clear();
                    this.loadFileList();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

    /**
     * 用途说明：处理清空回收站逻辑，发起异步任务并开始轮询进度
     * 入参说明：无
     * 返回值说明：无
     */
    async handleClearRecycleBin() {
        UIComponents.showConfirmModal({
            title: '清空回收站',
            message: '确定要清空回收站吗？这将永久删除回收站中的所有文件，此操作无法恢复！',
            confirmText: '确认清空',
            onConfirm: async () => {
                const response = await RecycleBinAPI.clearRecycleBin();
                if (response.status === 'success') {
                    Toast.show('已启动清空任务');
                    State.selectedPaths.clear();
                    State.isProcessing = true; 
                    this.checkTaskStatus();
                } else {
                    Toast.show(response.message);
                }
            }
        });
    },

    /**
     * 用途说明：循环检查当前删除/清空任务的状态
     * 入参说明：无
     * 返回值说明：无
     */
    async checkTaskStatus() {
        if (State.clearInterval) return;

        State.clearInterval = setInterval(async () => {
            try {
                const response = await RecycleBinAPI.getTaskProgress();
                if (response.status === 'success') {
                    const data = response.data;
                    if (data && data.status === 'processing') {
                        State.isProcessing = true;
                        UIController.toggleProcessingUI(true, data.progress.message);
                        UIController.updateProgress(data.progress);
                    } else if (data && data.status === 'idle') {
                        if (State.isProcessing) {
                            this.loadFileList();
                            Toast.show(data.progress.message || '操作已完成');
                        }
                        State.isProcessing = false;
                        this.stopTaskPolling();
                        UIController.toggleProcessingUI(false);
                    } else if (data && data.status === 'error') {
                        Toast.show(data.progress.message || '操作失败');
                        State.isProcessing = false;
                        this.stopTaskPolling();
                        UIController.toggleProcessingUI(false);
                    } else {
                        State.isProcessing = false;
                        this.stopTaskPolling();
                        UIController.toggleProcessingUI(false);
                    }
                } else {
                    State.isProcessing = false;
                    this.stopTaskPolling();
                    UIController.toggleProcessingUI(false);
                }
            } catch (e) {
                console.error('获取任务进度失败:', e);
                State.isProcessing = false;
                this.stopTaskPolling();
                UIController.toggleProcessingUI(false);
            }
        }, 1000);
    },

    /**
     * 用途说明：停止进度轮询
     * 入参说明：无
     * 返回值说明：无
     */
    stopTaskPolling() {
        if (State.clearInterval) {
            clearInterval(State.clearInterval);
            State.clearInterval = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
