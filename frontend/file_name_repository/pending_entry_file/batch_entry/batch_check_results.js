/**
 * 用途说明：批量录入检测结果展示页逻辑处理。
 * 模仿回收站页面风格，提供结果合并显示、分页逻辑、全选未收录项、点击表头排序及批量录入功能。
 */

// --- 状态管理 ---
const State = {
    /** @type {Object[]} 原始检测数据列表 [{name, source, detail}, ...] */
    fullData: [],
    /** @type {Object[]} 当前页显示的数据 */
    currentPageData: [],
    /** @type {Set<string>} 已选中的文件名集合 */
    selectedNames: new Set(),
    /** @type {number} 当前页码 */
    page: 1,
    /** @type {number} 每页数量 */
    limit: 20,
    /** @type {string} 排序字段 */
    sortBy: 'source',
    /** @type {string} 排序顺序 ASC/DESC */
    order: 'ASC',
    /** @type {Object} 分页控制器实例 */
    paginationController: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，模仿回收站风格。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 初始化顶部栏
        UIComponents.initRepoHeader({
            title: '批量录入检测结果',
            showSearch: false
        });

        this.elements = {
            tableBody: document.getElementById('results-list-body'),
            totalCount: document.getElementById('total-count'),
            newCount: document.getElementById('new-count'),
            selectAllNewBtn: document.getElementById('btn-select-all-new'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            btnConfirmImport: document.getElementById('btn-confirm-import'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

        // 初始化分页组件
        State.paginationController = UIComponents.initPagination('pagination-container', {
            limit: State.limit,
            onPageChange: (newPage) => {
                State.page = newPage;
                this.renderTable();
                window.scrollTo(0, 0);
            }
        });

        // 绑定通用表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedNames,
            idAttribute: 'data-id', // 这里对应渲染时 checkbox 的 data-id
            onSelectionChange: () => this.updateActionButtons()
        });

        // 绑定排序逻辑
        this.bindSortLogic();
    },

    /**
     * 用途说明：绑定表头排序逻辑。
     * 入参说明：无
     * 返回值说明：无
     */
    bindSortLogic() {
        const { sortableHeaders } = this.elements;
        sortableHeaders.forEach(th => {
            th.onclick = () => {
                const field = th.getAttribute('data-field');
                if (State.sortBy === field) {
                    State.order = State.order === 'ASC' ? 'DESC' : 'ASC';
                } else {
                    State.sortBy = field;
                    State.order = 'ASC';
                }
                UIComponents.updateSortUI(sortableHeaders, State.sortBy, State.order);
                App.sortAndRender();
            };
        });
    },

    /**
     * 用途说明：渲染表格内容。
     * 入参说明：无
     * 返回值说明：无
     */
    renderTable() {
        const { tableBody, totalCount, newCount, selectAllCheckbox } = this.elements;
        
        // 分页切片
        const start = (State.page - 1) * State.limit;
        const end = start + State.limit;
        State.currentPageData = State.fullData.slice(start, end);

        tableBody.innerHTML = '';
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        
        if (State.currentPageData.length === 0) {
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, '没有找到检测结果');
        } else {
            const fragment = document.createDocumentFragment();
            State.currentPageData.forEach((item, index) => {
                const isSelected = State.selectedNames.has(item.name);
                const tr = document.createElement('tr');
                tr.setAttribute('data-id', item.name); // 供 bindTableSelection 使用
                if (isSelected) tr.classList.add('selected-row');

                let statusHtml = '';
                if (item.source === 'new') {
                    statusHtml = '<span class="status-tag tag-new">未收录</span>';
                } else {
                    const sourceMap = {
                        'history': { class: 'tag-history', name: '曾录入库' },
                        'pending': { class: 'tag-pending', name: '待录入库' },
                        'index': { class: 'tag-index', name: '索引库' }
                    };
                    const config = sourceMap[item.source] || { class: 'tag-index', name: '索引库' };
                    
                    statusHtml = `
                        <span class="status-tag ${config.class}">
                            ${config.name}已存在
                        </span>${item.detail ? `<span class="status-detail-inline" title="${item.detail}"> (${item.detail})</span>` : ''}
                    `;
                }

                tr.innerHTML = `
                    <td class="col-index">${start + index + 1}</td>
                    <td class="col-name" title="${item.name}">${item.name}</td>
                    <td class="col-status">${statusHtml}</td>
                    <td class="col-check">
                        <input type="checkbox" class="file-checkbox" data-id="${item.name}" ${isSelected ? 'checked' : ''}>
                    </td>
                `;
                fragment.appendChild(tr);
            });
            tableBody.appendChild(fragment);
        }

        // 更新统计
        totalCount.textContent = State.fullData.length.toString();
        newCount.textContent = State.fullData.filter(i => i.source === 'new').length.toString();

        // 初始同步全选框状态
        if (State.currentPageData.length > 0 && selectAllCheckbox) {
            selectAllCheckbox.checked = State.currentPageData.every(item => State.selectedNames.has(item.name));
        }

        this.updateActionButtons();
        State.paginationController.update(State.fullData.length, State.page);
    },

    /**
     * 用途说明：更新操作按钮状态
     * 入参说明：无
     * 返回值说明：无
     */
    updateActionButtons() {
        const { btnConfirmImport } = this.elements;
        const selectedCount = State.selectedNames.size;
        btnConfirmImport.disabled = selectedCount === 0;
        btnConfirmImport.style.opacity = selectedCount === 0 ? '0.5' : '1';
        btnConfirmImport.textContent = `录入选中纪录 (${selectedCount})`;
    }
};

// --- API 交互模块 ---
const BatchAPI = {
    /**
     * 用途说明：批量录入文件名到待录入库。
     * 入参说明：fileNames {string[]}: 文件名数组; showMask {boolean}: 是否显示默认遮罩。
     * 返回值说明：Promise<Object>: 响应结果。
     */
    async saveToPendingRepo(fileNames, showMask = true) {
        return await Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames }, {}, showMask);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化结果页面。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.loadResultData();
        this.bindEvents();
    },

    /**
     * 用途说明：从本地存储加载检测结果并排序显示。
     * 入参说明：无
     * 返回值说明：无
     */
    loadResultData() {
        const rawData = sessionStorage.getItem('batch_check_results');
        if (!rawData) return;
        try {
            const data = JSON.parse(rawData);
            if (Array.isArray(data)) {
                State.fullData = data;
                this.sortAndRender();
                UIComponents.updateSortUI(UIController.elements.sortableHeaders, State.sortBy, State.order);
            }
        } catch (e) {
            console.error('加载检测结果失败:', e);
            Toast.show('数据解析异常');
        }
    },

    /**
     * 用途说明：对全量数据进行排序并触发渲染。
     * 入参说明：无
     * 返回值说明：无
     */
    sortAndRender() {
        const { sortBy, order } = State;
        State.fullData.sort((a, b) => {
            let valA = a[sortBy] || '';
            let valB = b[sortBy] || '';

            if (sortBy === 'source') {
                const getPriority = (s) => (s === 'new' ? '0' : '1') + s;
                valA = getPriority(valA);
                valB = getPriority(valB);
            }

            if (valA < valB) return order === 'ASC' ? -1 : 1;
            if (valA > valB) return order === 'ASC' ? 1 : -1;
            return 0;
        });
        State.page = 1;
        UIController.renderTable();
    },

    /**
     * 用途说明：绑定页面交互事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { selectAllNewBtn, btnConfirmImport } = UIController.elements;

        // 选中所有未收录
        if (selectAllNewBtn) {
            selectAllNewBtn.onclick = () => {
                const newNames = State.fullData
                    .filter(item => item.source === 'new')
                    .map(item => item.name);
                newNames.forEach(name => State.selectedNames.add(name));
                UIController.renderTable();
                Toast.show(`已选中 ${newNames.length} 个未收录项`);
            };
        }

        if (btnConfirmImport) {
            btnConfirmImport.onclick = () => this.handleBatchImport();
        }
    },

    /**
     * 用途说明：执行批量录入逻辑。
     * 入参说明：无
     * 返回值说明：无
     */
    async handleBatchImport() {
        const names = Array.from(State.selectedNames);
        if (names.length === 0) return;

        UIComponents.showConfirmModal({
            title: '确认录入',
            message: `确定要将选中的 ${names.length} 条记录录入“待录入库”吗？`,
            onConfirm: async () => {
                UIComponents.showProgressBar('.repo-container', '正在执行录入...');
                try {
                    const res = await BatchAPI.saveToPendingRepo(names, false);
                    if (res.status === 'success') {
                        Toast.show('录入成功！');
                        sessionStorage.removeItem('batch_check_results');
                        setTimeout(() => window.history.back(), 1000);
                    } else {
                        Toast.show('录入失败: ' + res.message);
                    }
                } finally {
                    UIComponents.hideProgressBar('.repo-container');
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
