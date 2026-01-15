/**
 * 用途说明：待录入文件名库页面逻辑处理，负责待录入文件名列表展示、分页、搜索及管理。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 20,
    sortBy: 'add_time',
    order: 'DESC',
    search: '',
    selectedIds: new Set(),
    paginationController: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，并使用公用组件初始化顶部栏
     */
    init() {
        // 使用公用组件初始化顶部栏
        UIComponents.initRepoHeader({
            searchPlaceholder: '搜索文件名...',
            showHistoryCheckbox: false,
            rightBtnText: '新增待录入',
            rightBtnId: 'btn-add-pending',
            onSearch: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('pending-entry-list-body'),
            searchInput: document.getElementById('search-input'),
            addPendingBtn: document.getElementById('btn-add-pending'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

        // 初始化分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadPendingList();
                window.scrollTo(0, 0);
            }
        });

        // 绑定表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedIds,
            idAttribute: 'data-id',
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
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, '暂无待录入文件名记录');
            return;
        }

        const startVisibleIndex = (State.page - 1) * State.limit + 1;

        list.forEach((item, index) => {
            const isChecked = State.selectedIds.has(String(item.id));
            const tr = document.createElement('tr');
            tr.setAttribute('data-id', item.id);
            if (isChecked) tr.classList.add('selected-row');

            tr.innerHTML = `
                <td class="col-index">${startVisibleIndex + index}</td>
                <td class="col-name">${item.file_name}</td>
                <td class="col-time">${item.add_time}</td>
                <td class="col-check">
                    <input type="checkbox" class="file-checkbox" data-id="${item.id}" ${isChecked ? 'checked' : ''}>
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
        const { deleteSelectedBtn } = this.elements;
        const count = State.selectedIds.size;

        if (count > 0) {
            deleteSelectedBtn.classList.remove('hidden');
            deleteSelectedBtn.textContent = `删除选中 (${count})`;
        } else {
            deleteSelectedBtn.classList.add('hidden');
        }
    }
};

// --- API 交互模块 ---
const PendingEntryAPI = {
    async getList(params) {
        const query = new URLSearchParams(params).toString();
        // 更新路径：/api/file_name_repository
        return await Request.get('/api/file_name_repository/pending_entry/list?' + query);
    },

    async addPending(fileNames) {
        // 更新路径：/api/file_name_repository
        return await Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames });
    },

    async batchDeletePending(ids) {
        // 更新路径：/api/file_name_repository
        return await Request.post('/api/file_name_repository/pending_entry/batch_delete', { ids: ids });
    },

    async clearPending() {
        // 更新路径：/api/file_name_repository
        return await Request.post('/api/file_name_repository/pending_entry/clear', {});
    }
};

// --- 应用逻辑主入口 ---
const App = {
    init() {
        UIController.init();
        this.bindEvents();
        this.loadPendingList();
    },

    bindEvents() {
        const { addPendingBtn, deleteSelectedBtn, sortableHeaders } = UIController.elements;

        if (addPendingBtn) {
            addPendingBtn.onclick = () => {
                UIComponents.showInputModal({
                    title: '新增待录入文件名',
                    placeholder: '请输入文件名（多个请用换行或逗号分隔）',
                    isTextArea: true,
                    onConfirm: async (value) => {
                        const names = value.split(/[\n,，]/).map(n => n.trim()).filter(n => n);
                        if (names.length === 0) return;
                        const res = await PendingEntryAPI.addPending(names);
                        if (res.status === 'success') {
                            Toast.show('添加成功');
                            this.loadPendingList();
                        } else {
                            Toast.show(res.message);
                        }
                    }
                });
            };
        }

        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleDeleteSelected();
        }

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
                this.loadPendingList();
            };
        });
    },

    handleSearch() {
        const { searchInput } = UIController.elements;
        State.search = searchInput.value.trim();
        State.page = 1;
        State.selectedIds.clear();
        this.loadPendingList();
    },

    async loadPendingList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };
        const res = await PendingEntryAPI.getList(params);
        if (res.status === 'success' && res.data) {
            UIController.renderTable(res.data.list);
            State.paginationController.update(res.data.total, res.data.page);
        } else {
            Toast.show(res.message || '加载列表失败');
        }
    },

    async handleDeleteSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        UIComponents.showConfirmModal({
            title: '删除选中记录',
            message: `确定要移除选中的 ${ids.length} 条记录吗？`,
            onConfirm: async () => {
                const res = await PendingEntryAPI.batchDeletePending(ids);
                if (res.status === 'success') {
                    Toast.show('已删除');
                    State.selectedIds.clear();
                    this.loadPendingList();
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
