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
    paginationController: null,
    linkPrefix: '', // 文件名跳转前缀
    currentList: [], // 当前页面的数据列表
    defaultInterval: 2000 // 默认打开链接的间隔时间（毫秒）
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
            rightBtnText: '批量录入新数据',
            rightBtnId: 'btn-go-batch',
            onSearch: () => App.handleSearch()
        });

        this.elements = {
            tableBody: document.getElementById('pending-entry-list-body'),
            searchInput: document.getElementById('search-input'),
            goBatchBtn: document.getElementById('btn-go-batch'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            openAndMoveBtn: document.getElementById('btn-open-and-move'),
            moveToAlreadyEnteredBtn: document.getElementById('btn-move-to-already-entered'), // 移到已收录按钮
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
     * 入参说明：list: Array - 待录入记录列表数据
     * 返回值说明：无
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
        const fragment = document.createDocumentFragment();

        list.forEach((item, index) => {
            const isChecked = State.selectedIds.has(String(item.id));
            const tr = document.createElement('tr');
            tr.setAttribute('data-id', item.id);
            if (isChecked) tr.classList.add('selected-row');

            // 根据是否有前缀决定文件名渲染方式
            const nameDisplay = State.linkPrefix 
                ? `<a href="${State.linkPrefix}${encodeURIComponent(item.file_name)}" target="_blank" class="file-link">${item.file_name}</a>`
                : item.file_name;

            tr.innerHTML = `
                <td class="col-index">${startVisibleIndex + index}</td>
                <td class="col-name">${nameDisplay}</td>
                <td class="col-time">${item.add_time}</td>
                <td class="col-check">
                    <input type="checkbox" class="file-checkbox" data-id="${item.id}" ${isChecked ? 'checked' : ''}>
                </td>
            `;
            fragment.appendChild(tr);
        });
        tableBody.appendChild(fragment);

        this.updateActionButtons();
    },

    /**
     * 用途说明：更新表头排序 UI 状态
     * 入参说明：field: string - 排序字段名; order: string - 排序方向 ('ASC' 或 'DESC')
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：更新操作按钮的启用/禁用或可见状态
     * 入参说明：无
     * 返回值说明：无
     */
    updateActionButtons() {
        const { deleteSelectedBtn, openAndMoveBtn, moveToAlreadyEnteredBtn } = this.elements;
        const count = State.selectedIds.size;

        if (count > 0) {
            deleteSelectedBtn.classList.remove('hidden');
            deleteSelectedBtn.textContent = `删除选中 (${count})`;
            if (openAndMoveBtn) openAndMoveBtn.classList.remove('hidden');
            if (moveToAlreadyEnteredBtn) moveToAlreadyEnteredBtn.classList.remove('hidden');
        } else {
            deleteSelectedBtn.classList.add('hidden');
            if (openAndMoveBtn) openAndMoveBtn.classList.add('hidden');
            if (moveToAlreadyEnteredBtn) moveToAlreadyEnteredBtn.classList.add('hidden');
        }
    }
};

// --- API 交互模块 ---
const PendingEntryAPI = {
    /**
     * 用途说明：获取待录入文件名列表
     * 入参说明：params: Object - 查询参数 (page, limit, sort_by, order_asc, search)
     * 返回值说明：Promise - 返回包含状态 and 数据的对象
     */
    async getList(params) {
        const query = new URLSearchParams(params).toString();
        return await Request.get('/api/file_name_repository/pending_entry/list?' + query);
    },

    /**
     * 用途说明：批量删除待录入记录
     * 入参说明：ids: Array - 记录 ID 列表
     * 返回值说明：Promise - 返回操作结果状态
     */
    async batchDeletePending(ids) {
        return await Request.post('/api/file_name_repository/pending_entry/batch_delete', { ids: ids });
    },

    /**
     * 用途说明：批量添加曾录入记录
     * 入参说明：fileNames: Array - 文件名列表
     * 返回值说明：Promise - 返回操作结果状态
     */
    async addToAlreadyEntered(fileNames) {
        return await Request.post('/api/file_name_repository/already_entered/add', { file_names: fileNames });
    },

    /**
     * 用途说明：获取系统配置
     * 返回值说明：Promise<Object> - 配置数据
     */
    async getSettings() {
        return await Request.get('/api/setting/get');
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：应用初始化入口
     * 入参说明：无
     * 返回值说明：无
     */
    async init() {
        UIController.init();
        this.bindEvents();
        await this.loadConfig(); // 先加载配置
        this.loadPendingList();
    },

    /**
     * 用途说明：加载系统配置以获取链接前缀
     * 入参说明：无
     * 返回值说明：无
     */
    async loadConfig() {
        try {
            const res = await PendingEntryAPI.getSettings();
            if (res.status === 'success' && res.data && res.data.file_name_entry) {
                State.linkPrefix = res.data.file_name_entry.file_name_link_prefix || '';
            }
        } catch (e) {
            console.error('加载配置失败:', e);
        }
    },

    /**
     * 用途说明：绑定页面交互事件，并监听页面可见性变化以刷新数据
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { goBatchBtn, deleteSelectedBtn, openAndMoveBtn, moveToAlreadyEnteredBtn, sortableHeaders } = UIController.elements;

        if (goBatchBtn) {
            goBatchBtn.onclick = () => {
                window.location.href = 'batch_entry/batch_entry.html';
            };
        }

        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => this.handleDeleteSelected();
        }

        if (openAndMoveBtn) {
            openAndMoveBtn.onclick = () => this.handleOpenAndMoveSelected();
        }
        
        if (moveToAlreadyEnteredBtn) {
            moveToAlreadyEnteredBtn.onclick = () => this.handleMoveToAlreadyEntered();
        }

        sortableHeaders.forEach(th => {
            th.onclick = () => {
                const field = th.getAttribute('data-field');
                State.order = (State.sortBy === field && State.order === 'ASC') ? 'DESC' : 'ASC';
                State.sortBy = field;
                UIController.updateSortUI(State.sortBy, State.order);
                this.loadPendingList();
            };
        });

        // 监听页面回到前台或从缓存恢复时刷新数据
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                this.loadPendingList();
            }
        });

        // 监听页面可见性变化，当用户切回该标签页时刷新
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                this.loadPendingList();
            }
        });
    },

    /**
     * 用途说明：执行搜索操作
     * 入参说明：无
     * 返回值说明：无
     */
    handleSearch() {
        const { searchInput } = UIController.elements;
        State.search = searchInput.value.trim();
        State.page = 1;
        State.selectedIds.clear();
        this.loadPendingList();
    },

    /**
     * 用途说明：加载并渲染待录入文件名列表
     * 入参说明：无
     * 返回值说明：无
     */
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
            State.currentList = res.data.list;
            UIController.renderTable(res.data.list);
            State.paginationController.update(res.data.total, res.data.page);
        } else {
            Toast.show(res.message || '加载列表失败');
        }
    },

    /**
     * 用途说明：处理批量删除选中项的操作
     * 入参说明：无
     * 返回值说明：无
     */
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
    },

    /**
     * 用途说明：处理“启动录入”操作：逐个在后台打开网页链接
     * 入参说明：无
     * 返回值说明：无
     */
    async handleOpenAndMoveSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        const selectedFiles = State.currentList.filter(item => State.selectedIds.has(String(item.id)));
        
        if (selectedFiles.length === 0) {
            Toast.show('未找到选中数据');
            return;
        }

        // 提示并输入间隔时间
        UIComponents.showInputModal({
            title: '打开网址',
            placeholder: String(State.defaultInterval),
            onConfirm: async (value) => {
                let interval = parseInt(value);
                if (isNaN(interval) || interval < 0) interval = State.defaultInterval;

                Toast.show(`准备打开 ${selectedFiles.length} 个链接，间隔 ${interval}ms`);

                // 1. 逐个打开网页
                for (let i = 0; i < selectedFiles.length; i++) {
                    const item = selectedFiles[i];
                    const url = State.linkPrefix + encodeURIComponent(item.file_name);
                    
                    if (i > 0) {
                        await new Promise(resolve => setTimeout(resolve, interval));
                    }
                    
                    // 在新标签页中打开（尝试不切换标签页：立即将焦点切回父窗口）
                    const newWin = window.open(url, '_blank');
                    if (newWin) {
                        window.focus();
                    }
                }
            }
        });
        
        // 动态调整弹窗：增加确认说明文字和输入框前面的标签
        const modalEl = document.getElementById('common-input-modal');
        if (modalEl) {
            const group = modalEl.querySelector('.modal-input-group');
            if (group) {
                // 1. 增加确认提示文字
                const msgEl = document.createElement('p');
                msgEl.className = 'modal-msg';
                msgEl.style.marginBottom = '15px';
                msgEl.textContent = `确认将逐个打开选中的 ${selectedFiles.length} 个文件名的网页链接吗？`;
                group.parentNode.insertBefore(msgEl, group);

                // 2. 在输入框前添加提示标签
                const labelEl = document.createElement('label');
                labelEl.textContent = '打开间隔(毫秒)：';
                labelEl.style.fontSize = '14px';
                labelEl.style.display = 'block';
                labelEl.style.marginBottom = '8px';
                labelEl.style.color = '#3c4043';
                labelEl.style.fontWeight = '500';
                group.insertBefore(labelEl, group.firstChild);
            }
            
            // 设置默认值
            const inputEl = document.getElementById('common-modal-input');
            if (inputEl) {
                inputEl.value = String(State.defaultInterval);
                inputEl.style.marginTop = '0';
            }
        }
    },

    /**
     * 用途说明：处理“移到已收录”操作：将选中的文件名批量转移到曾录入文件名库
     * 入参说明：无
     * 返回值说明：无
     */
    async handleMoveToAlreadyEntered() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        const selectedFiles = State.currentList.filter(item => State.selectedIds.has(String(item.id)));

        if (selectedFiles.length === 0) {
            Toast.show('未找到选中数据');
            return;
        }

        UIComponents.showConfirmModal({
            title: '移到已收录',
            message: `确认将选中的 ${selectedFiles.length} 条记录转移到“曾录入文件名库”吗？`,
            onConfirm: async () => {
                const fileNames = selectedFiles.map(f => f.file_name);
                try {
                    const addRes = await PendingEntryAPI.addToAlreadyEntered(fileNames);
                    if (addRes.status === 'success') {
                        const delRes = await PendingEntryAPI.batchDeletePending(ids);
                        if (delRes.status === 'success') {
                            Toast.show('已成功移入曾录入库');
                            State.selectedIds.clear();
                            this.loadPendingList();
                        } else {
                            Toast.show('已添加至曾录入库，但从待录入库移除失败');
                        }
                    } else {
                        Toast.show('转移失败: ' + (addRes.message || '未知错误'));
                    }
                } catch (e) {
                    console.error('移库失败:', e);
                    Toast.show('操作过程中出现异常');
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
