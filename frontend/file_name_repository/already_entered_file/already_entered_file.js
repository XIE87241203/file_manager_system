/**
 * 用途说明：曾录入文件名库页面逻辑处理，负责曾录入文件名列表展示、分页、搜索及管理。
 */

// --- 状态管理 ---
const State = {
    page: 1,
    limit: 20,
    sortBy: 'add_time',
    order: 'DESC',
    search: '',
    selectedIds: new Set(),
    linkPrefix: '' // 文件名跳转前缀
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，并使用 SearchHeaderToolbar 初始化顶部栏
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用 SearchHeaderToolbar 组件初始化顶部栏
        SearchHeaderToolbar.init({
            searchHint: '搜索文件名...',
            menuIcon: "../../common/header_toolbar/icon/add_icon.svg",
            searchCallback: (content) => {
                State.search = content;
                App.handleSearch();
            },
            menuCallback: () => {
                App.handleAddAlreadyEntered();
            }
        });

        this.elements = {
            tableBody: document.getElementById('already-entered-list-body'),
            // 搜索输入框 ID 由 SearchHeaderToolbar 定义
            searchInput: document.getElementById('search-input'),
            deleteSelectedBtn: document.getElementById('btn-delete-selected'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

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
     * 入参说明：list: Array - 文件名记录数组
     * 返回值说明：无
     */
    renderTable(list) {
        const { tableBody, selectAllCheckbox } = this.elements;
        tableBody.innerHTML = '';
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        if (!list || list.length === 0) {
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, '暂无曾录入文件名记录');
            return;
        }

        const startVisibleIndex = (State.page - 1) * State.limit + 1;

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
            tableBody.appendChild(tr);
        });

        this.updateActionButtons();
    },

    /**
     * 用途说明：更新排序 UI 状态
     * 入参说明：field: string - 排序字段; order: string - 排序方式
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    },

    /**
     * 用途说明：更新底部操作按钮（如删除选中）的状态
     * 入参说明：无
     * 返回值说明：无
     */
    updateActionButtons() {
        const { deleteSelectedBtn } = this.elements;
        if (!deleteSelectedBtn) return;

        const count = State.selectedIds.size;
        if (count > 0) {
            deleteSelectedBtn.classList.remove('hidden');
        } else {
            deleteSelectedBtn.classList.add('hidden');
        }
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：程序初始化入口
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        this.loadConfig(() => {
            this.loadList();
        });
    },

    /**
     * 用途说明：加载系统配置以获取链接前缀
     * 入参说明：callback: Function - 加载完成后的回调
     * 返回值说明：无
     */
    loadConfig(callback) {
        AlreadyEnteredAPI.getSettings(
            (data) => {
                if (data && data.file_name_entry) {
                    State.linkPrefix = data.file_name_entry.file_name_link_prefix || '';
                }
                callback && callback();
            },
            (err) => {
                console.error('加载配置失败:', err);
                callback && callback();
            }
        );
    },

    /**
     * 用途说明：绑定页面交互事件
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { deleteSelectedBtn, sortableHeaders } = UIController.elements;

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
                this.loadList();
            };
        });
    },

    /**
     * 用途说明：处理新增曾录入文件名操作
     * 入参说明：无
     * 返回值说明：无
     */
    handleAddAlreadyEntered() {
        UIComponents.showInputModal({
            title: '新增曾录入文件名',
            placeholder: '请输入文件名（多个请用换行或逗号分隔）',
            isTextArea: true,
            onConfirm: (value) => {
                const names = value.split(/[\n,，]/).map(n => n.trim()).filter(n => n);
                if (names.length === 0) return;
                AlreadyEnteredAPI.add(names, (res) => {
                    Toast.show('添加成功');
                    this.loadList();
                }, (msg) => {
                    Toast.show(msg);
                });
            }
        });
    },

    /**
     * 用途说明：处理搜索触发
     * 入参说明：无
     * 返回值说明：无
     */
    handleSearch() {
        State.page = 1;
        State.selectedIds.clear();
        this.loadList();
    },

    /**
     * 用途说明：从服务器加载列表数据
     * 入参说明：无
     * 返回值说明：无
     */
    loadList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };

        AlreadyEnteredAPI.getList(params, (data) => {
            UIController.renderTable(data.list);

            // 使用公共 PageBar 组件渲染分页栏
            PageBar.init({
                containerId: 'pagination-container',
                totalItems: data.total,
                pageSize: State.limit,
                currentPage: data.page,
                onPageChange: (newPage) => {
                    State.page = newPage;
                    this.loadList();
                    window.scrollTo(0, 0);
                }
            });
        }, (msg) => {
            Toast.show(msg || '加载列表失败');
        });
    },

    /**
     * 用途说明：处理批量删除选中记录
     * 入参说明：无
     * 返回值说明：无
     */
    handleDeleteSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        UIComponents.showConfirmModal({
            title: '删除选中记录',
            message: `确定要移除选中的 ${ids.length} 条记录吗？`,
            onConfirm: () => {
                AlreadyEnteredAPI.batchDelete(ids, (res) => {
                    Toast.show('已删除');
                    State.selectedIds.clear();
                    this.loadList();
                }, (msg) => {
                    Toast.show(msg);
                });
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
