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
    paginationController: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器
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
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        if (!list || list.length === 0) {
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(6, '回收站空空如也');
            return;
        }

        list.forEach(file => {
            const isChecked = State.selectedPaths.has(file.file_path);
            const tr = document.createElement('tr');
            tr.setAttribute('data-path', file.file_path);
            if (isChecked) tr.classList.add('selected-row');

            const fileName = UIComponents.getFileName(file.file_path);
            const fileSizeStr = CommonUtils.formatFileSize(file.file_size);

            tr.innerHTML = `
                <td class="col-name" title="${fileName}">${fileName}</td>
                <td class="col-size">${fileSizeStr}</td>
                <td class="col-path" title="${file.file_path}">${file.file_path}</td>
                <td class="col-md5"><code>${file.file_md5}</code></td>
                <td class="col-time">${file.recycle_bin_time}</td>
                <td class="col-check">
                    <input type="checkbox" class="file-checkbox" data-path="${file.file_path}" ${isChecked ? 'checked' : ''}>
                </td>
            `;
            tableBody.appendChild(tr);
        });
        
        this.updateActionButtons();
    },

    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

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
    async getList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get('/api/file_repository/list?is_in_recycle_bin=true&' + query);
    },

    async restoreFiles(filePaths) {
        return await Request.post('/api/file_repository/restore_from_recycle_bin', { file_paths: filePaths });
    },

    async deleteFiles(filePaths) {
        // 彻底删除进度条开启时，禁用默认 mask
        return await Request.post('/api/file_repository/clear_recycle_bin', { file_paths: filePaths }, {}, false);
    },

    async clearAll() {
        // 清空进度条开启时，禁用默认 mask
        return await Request.post('/api/file_repository/clear_recycle_bin', {}, {}, false);
    },

    async getDeleteProgress() {
        // 轮询进度时一律不显示 mask，防止页面抖动
        return await Request.get('/api/file_repository/clear_recycle_bin/progress', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    init() {
        UIController.init();
        this.bindEvents();
        this.loadFileList();
        this.checkTaskStatus();
    },

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

    handleSearch() {
        const { searchInput } = UIController.elements;
        State.search = searchInput.value.trim();
        State.page = 1;
        State.selectedPaths.clear();
        this.loadFileList();
    },

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

    startProgressPolling() {
        UIComponents.showProgressBar('.repo-container', '正在删除文件...');
        const timer = setInterval(async () => {
            const res = await RecycleBinAPI.getDeleteProgress();
            if (res.status === 'success') {
                const data = res.data;
                if (data.status === ProgressStatus.PROCESSING) {
                    UIComponents.renderProgress('.repo-container', data.progress);
                } else {
                    clearInterval(timer);
                    UIComponents.hideProgressBar('.repo-container');
                    if (data.status === ProgressStatus.COMPLETED) {
                        Toast.show('处理完成');
                        State.selectedPaths.clear();
                        this.loadFileList();
                    }
                }
            } else {
                clearInterval(timer);
                UIComponents.hideProgressBar('.repo-container');
            }
        }, 1000);
    },

    async checkTaskStatus() {
        const res = await RecycleBinAPI.getDeleteProgress();
        if (res.status === 'success' && res.data.status === ProgressStatus.PROCESSING) {
            this.startProgressPolling();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
