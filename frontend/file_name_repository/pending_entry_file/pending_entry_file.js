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
        // 使用公用组件初始化搜索顶部栏
        SearchHeaderToolbar.init({
            searchHint: I18nManager.t('pending_entry.search_hint'),
            menuIcon: "../../common/header_toolbar/icon/add_icon.svg",
            searchCallback: (content) => {
                State.search = content;
                App.handleSearch();
            },
            menuCallback: () => {
                window.location.href = 'batch_entry/batch_entry.html';
            }
        });

        this.elements = {
            tableBody: document.getElementById('pending-entry-list-body'),
            searchInput: document.getElementById('search-input'),
            // 改为下拉菜单中的 ID
            deleteSelectedBtn: document.getElementById('menu-delete-selected'),
            openAndMoveBtn: document.getElementById('menu-open-and-move'),
            moveToAlreadyEnteredBtn: document.getElementById('menu-move-to-already-entered'),
            footerMenuBtn: document.getElementById('btn-footer-menu'),
            footerMenu: document.getElementById('footer-dropdown-menu'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

        // 绑定表格选择逻辑
        UIComponents.bindTableSelection({
            tableBody: this.elements.tableBody,
            selectAllCheckbox: this.elements.selectAllCheckbox,
            selectedSet: State.selectedIds,
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
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, I18nManager.t('pending_entry.no_data'));
            return;
        }

        const startVisibleIndex = (State.page - 1) * State.limit + 1;
        const fragment = document.createDocumentFragment();

        list.forEach((item, index) => {
            const isChecked = State.selectedIds.has(String(item.id));
            const tr = document.createElement('tr');
            tr.setAttribute('data-id', item.id);
            if (isChecked) tr.classList.add('selected-row');

            // 根据是否有前缀决定文件名渲染方式，并添加 title 属性用于悬停显示全名
            const nameDisplay = State.linkPrefix 
                ? `<a href="${State.linkPrefix}${encodeURIComponent(item.file_name)}" target="_blank" class="file-link max-two-line" title="${item.file_name}">${item.file_name}</a>`
                : `<span class="max-two-line" title="${item.file_name}">${item.file_name}</span>`;

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
        const { footerMenuBtn, deleteSelectedBtn } = this.elements;
        const count = State.selectedIds.size;

        if (count > 0) {
            footerMenuBtn.classList.remove('hidden');
            if (deleteSelectedBtn) {
                deleteSelectedBtn.textContent = I18nManager.t('common.delete_selected_count', { count: count });
            }
        } else {
            footerMenuBtn.classList.add('hidden');
            this.toggleFooterMenu(false);
        }
    },

    /**
     * 用途说明：切换底部下拉菜单的显示状态
     * 入参说明：show: boolean - 是否显示
     * 返回值说明：无
     */
    toggleFooterMenu(show) {
        const { footerMenu, footerMenuBtn } = this.elements;
        if (!footerMenu || !footerMenuBtn) return;

        if (show) {
            const rect = footerMenuBtn.getBoundingClientRect();
            // 定位在按钮上方
            footerMenu.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
            footerMenu.style.right = (window.innerWidth - rect.right) + 'px';
            footerMenu.classList.add('show');
        } else {
            footerMenu.classList.remove('show');
        }
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
        // 初始化多语言
        I18nManager.init();
        I18nManager.render();

        UIController.init();
        this.bindEvents();
        this.loadConfig(); // 加载配置
        this.loadPendingList();
    },

    /**
     * 用途说明：加载系统配置以获取链接前缀
     * 入参说明：无
     * 返回值说明：无
     */
    loadConfig() {
        PendingEntryAPI.getSettings(
            (data) => {
                if (data && data.file_name_entry) {
                    State.linkPrefix = data.file_name_entry.file_name_link_prefix || '';
                }
            },
            (err) => console.error(I18nManager.t('common.error'), err)
        );
    },

    /**
     * 用途说明：绑定页面交互事件，并监听页面可见性变化以刷新数据
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const {
            deleteSelectedBtn, openAndMoveBtn, moveToAlreadyEnteredBtn,
            sortableHeaders, footerMenuBtn, footerMenu
        } = UIController.elements;

        // 绑定底部菜单按钮
        if (footerMenuBtn) {
            footerMenuBtn.onclick = (e) => {
                e.stopPropagation();
                const isShow = footerMenu.classList.contains('show');
                UIController.toggleFooterMenu(!isShow);
            };
        }

        // 点击页面其他地方关闭菜单
        document.addEventListener('click', () => {
            UIController.toggleFooterMenu(false);
        });

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
        State.page = 1;
        State.selectedIds.clear();
        this.loadPendingList();
    },

    /**
     * 用途说明：加载并渲染待录入文件名列表
     * 入参说明：无
     * 返回值说明：无
     */
    loadPendingList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };
        PendingEntryAPI.getList(
            params,
            (data) => {
                State.currentList = data.list;
                UIController.renderTable(data.list);

                // 使用公共 PageBar 组件渲染分页栏
                PageBar.init({
                    containerId: 'pagination-container',
                    totalItems: data.total,
                    pageSize: State.limit,
                    currentPage: data.page,
                    onPageChange: (newPage) => {
                        State.page = newPage;
                        this.loadPendingList();
                        window.scrollTo(0, 0);
                    }
                });
            },
            (err) => Toast.show(err || I18nManager.t('pending_entry.load_failed'))
        );
    },

    /**
     * 用途说明：处理批量删除选中项的操作
     * 入参说明：无
     * 返回值说明：无
     */
    handleDeleteSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        UIComponents.showConfirmModal({
            title: I18nManager.t('already_entered.delete_confirm_title'),
            message: I18nManager.t('already_entered.delete_confirm_msg', { count: ids.length }),
            onConfirm: () => {
                PendingEntryAPI.batchDeletePending(
                    ids,
                    () => {
                        Toast.show(I18nManager.t('common.deleted'));
                        State.selectedIds.clear();
                        this.loadPendingList();
                    },
                    (err) => Toast.show(err || I18nManager.t('common.error'))
                );
            }
        });
    },

    /**
     * 用途说明：处理“启动录入”操作：逐个在后台打开网页链接
     * 入参说明：无
     * 返回值说明：无
     */
    handleOpenAndMoveSelected() {
        const ids = Array.from(State.selectedIds).map(id => parseInt(id));
        const selectedFiles = State.currentList.filter(item => State.selectedIds.has(String(item.id)));
        
        if (selectedFiles.length === 0) {
            Toast.show(I18nManager.t('pending_entry.no_selected'));
            return;
        }

        // 提示并输入间隔时间
        UIComponents.showInputModal({
            title: I18nManager.t('pending_entry.open_url'),
            placeholder: String(State.defaultInterval),
            onConfirm: async (value) => {
                let interval = parseInt(value);
                if (isNaN(interval) || interval < 0) interval = State.defaultInterval;

                Toast.show(I18nManager.t('pending_entry.batch_open_toast', { count: selectedFiles.length, interval: interval }));

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
                msgEl.textContent = I18nManager.t('pending_entry.batch_open_confirm', { count: selectedFiles.length });
                group.parentNode.insertBefore(msgEl, group);

                // 2. 在输入框前添加提示标签
                const labelEl = document.createElement('label');
                labelEl.textContent = I18nManager.t('pending_entry.interval_label');
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
     * 用途说明：直接将选中的待录入记录移入“曾录入”库
     * 入参说明：无
     * 返回值说明：无
     */
    handleMoveToAlreadyEntered() {
        const selectedFiles = State.currentList.filter(item => State.selectedIds.has(String(item.id)));
        const names = selectedFiles.map(f => f.file_name);
        const ids = selectedFiles.map(f => f.id);

        if (names.length === 0) {
            Toast.show(I18nManager.t('pending_entry.no_selected'));
            return;
        }

        PendingEntryAPI.addToAlreadyEntered(names, () => {
            // 成功加入曾录入后，从待录入中删除
            PendingEntryAPI.batchDeletePending(ids, () => {
                Toast.show(I18nManager.t('pending_entry.move_success'));
                State.selectedIds.clear();
                this.loadPendingList();
            }, (err) => Toast.show(err));
        }, (err) => Toast.show(err));
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
