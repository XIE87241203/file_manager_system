/**
 * 用途说明：忽略文件库页面逻辑处理，负责忽略文件名列表展示、分页、搜索及管理。
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
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用公用组件初始化顶部栏
        UIComponents.initRepoHeader({
            searchPlaceholder: '搜索文件名...',
            showHistoryCheckbox: false,
            rightBtnText: '新增忽略',
            rightBtnId: 'btn-add-ignore',
            onSearch: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('ignore-list-body'),
            searchInput: document.getElementById('search-input'),
            addIgnoreBtn: document.getElementById('btn-add-ignore'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

        // 初始化分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                App.loadIgnoreList();
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
     * 入参说明：list (Array) - 忽略文件数据列表
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        if (!list || list.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 100px; color: #9aa0a6;">暂无忽略文件记录</td></tr>`;
            return;
        }

        // 计算当前页起始序号
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

    /**
     * 用途说明：更新表头排序图标
     * 入参说明：field (String) - 排序字段名，order (String) - 排序方向 (ASC/DESC)
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：更新操作按钮显示状态
     */
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
const IgnoreAPI = {
    /**
     * 用途说明：获取忽略文件列表
     * 入参说明：params (Object) - 分页及搜索参数
     * 返回值说明：Promise - 返回后端统一响应格式的数据
     */
    async getList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get('/api/file_repository/ignore/list?' + query);
    },

    /**
     * 用途说明：批量添加忽略文件名
     * 入参说明：fileNames (Array) - 文件名字符串数组
     * 返回值说明：Promise - 操作结果
     */
    async addIgnore(fileNames) {
        return await Request.post('/api/file_repository/ignore/add', { file_names: fileNames });
    },


    /**
     * 用途说明：批量删除忽略文件记录
     * 入参说明：ids (Array) - ID 列表
     * 返回值说明：Promise - 操作结果
     */
    async batchDeleteIgnore(ids) {
        return await Request.post('/api/file_repository/ignore/batch_delete', { ids: ids });
    },

    /**
     * 用途说明：清空所有忽略规则
     * 入参说明：无
     * 返回值说明：Promise - 操作结果
     */
    async clearIgnore() {
        return await Request.post('/api/file_repository/ignore/clear', {});
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：应用初始化入口
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadIgnoreList();
    },

    /**
     * 用途说明：绑定页面交互事件
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { addIgnoreBtn, deleteSelectedBtn, sortableHeaders } = UIController.elements;

        // 新增忽略逻辑
        if (addIgnoreBtn) {
            addIgnoreBtn.onclick = () => {
                UIComponents.showInputModal({
                    title: '新增忽略文件',
                    placeholder: '请输入文件名（多个请用换行或逗号分隔）',
                    isTextArea: true,
                    onConfirm: async (value) => {
                        const names = value.split(/[\n,，]/).map(n => n.trim()).filter(n => n);
                        if (names.length === 0) return;
                        const res = await IgnoreAPI.addIgnore(names);
                        if (res.status === 'success') {
                            Toast.show('添加成功');
                            this.loadIgnoreList();
                        } else {
                            Toast.show(res.message);
                        }
                    }
                });
            };
        }

        // 删除选中逻辑
        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleDeleteSelected();
        }

        // 排序逻辑绑定
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
                this.loadIgnoreList();
            };
        });
    },

    /**
     * 用途说明：处理搜索指令
     * 入参说明：无
     * 返回值说明：无
     */
    handleSearch() {
        const { searchInput } = UIController.elements;
        State.search = searchInput.value.trim();
        State.page = 1;
        State.selectedIds.clear();
        this.loadIgnoreList();
    },

    /**
     * 用途说明：请求后端并加载忽略文件数据
     * 入参说明：无
     * 返回值说明：无
     */
    async loadIgnoreList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };
        const res = await IgnoreAPI.getList(params);
        if (res.status === 'success' && res.data) {
            UIController.renderTable(res.data.list);
            // 确保使用后端返回的最新分页信息进行更新
            State.paginationController.update(res.data.total, res.data.page);
        } else {
            Toast.show(res.message || '加载列表失败');
        }
    },

    /**
     * 用途说明：执行批量删除
     */
    async handleDeleteSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        UIComponents.showConfirmModal({
            title: '删除选中记录',
            message: `确定要移除选中的 ${ids.length} 条忽略规则吗？`,
            onConfirm: async () => {
                const res = await IgnoreAPI.batchDeleteIgnore(ids);
                if (res.status === 'success') {
                    Toast.show('已删除');
                    State.selectedIds.clear();
                    this.loadIgnoreList();
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
