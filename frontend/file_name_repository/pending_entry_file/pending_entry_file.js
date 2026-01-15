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
            rightBtnText: '批量录入新数据',
            rightBtnId: 'btn-go-batch',
            onSearch: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('pending-entry-list-body'),
            searchInput: document.getElementById('search-input'),
            goBatchBtn: document.getElementById('btn-go-batch'),
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
        return await Request.get('/api/file_name_repository/pending_entry/list?' + query);
    },

    async batchDeletePending(ids) {
        return await Request.post('/api/file_name_repository/pending_entry/batch_delete', { ids: ids });
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
        const { goBatchBtn, deleteSelectedBtn, sortableHeaders } = UIController.elements;

        // 跳转到新设计的批量录入页面
        if (goBatchBtn) {
            goBatchBtn.onclick = () => {
                window.location.href = 'batch_entry.html';
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
