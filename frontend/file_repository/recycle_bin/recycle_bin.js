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
        // 使用搜索型顶部工具栏初始化顶部栏
        SearchHeaderToolbar.init({
            searchHint: '搜索文件名 (正则模糊匹配)...',
            searchCallback: (content) => App.handleSearch(content)
        });

        this.elements = {
            tableBody: document.getElementById('file-list-body'),
            searchInput: document.getElementById('search-input'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            restoreSelectedBtn: document.getElementById('menu-restore-selected'),
            deleteSelectedBtn: document.getElementById('menu-delete-selected'),
            footerMenuBtn: document.getElementById('btn-recycle-action'),
            footerMenu: document.getElementById('footer-dropdown-menu'),
            sortableHeaders: document.querySelectorAll('th.sortable')
        };

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
            this.updateActionButtons();
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
        const { restoreSelectedBtn, deleteSelectedBtn, footerMenuBtn } = this.elements;
        const count = State.selectedPaths.size;

        if (count > 0) {
            restoreSelectedBtn.textContent = `恢复选中 (${count})`;
            deleteSelectedBtn.textContent = `彻底删除 (${count})`;
        } else {
            restoreSelectedBtn.textContent = '恢复选中';
            deleteSelectedBtn.textContent = '彻底删除选中';
            if (footerMenuBtn) {
                this.toggleFooterMenu(false);
            }
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
        const { restoreSelectedBtn, deleteSelectedBtn, footerMenuBtn, footerMenu, sortableHeaders } = UIController.elements;
        if (restoreSelectedBtn) {
            restoreSelectedBtn.onclick = () => {
                UIController.toggleFooterMenu(false);
                this.handleRestore();
            };
        }
        if (deleteSelectedBtn) {
            deleteSelectedBtn.onclick = () => {
                UIController.toggleFooterMenu(false);
                this.handleDeleteSelected();
            };
        }

        if (footerMenuBtn) {
            footerMenuBtn.onclick = (event) => {
                event.stopPropagation();
                const count = State.selectedPaths.size;
                if (count > 0 && footerMenu) {
                    const isShow = footerMenu.classList.contains('show');
                    UIController.toggleFooterMenu(!isShow);
                } else {
                    UIController.toggleFooterMenu(false);
                    this.handleClearAll();
                }
            };
        }

        document.addEventListener('click', () => {
            UIController.toggleFooterMenu(false);
        });

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
     * 入参说明：searchContent: 搜索内容字符串（来自顶部工具栏回调，可选）
     * 返回值说明：无
     */
    handleSearch(searchContent) {
        const { searchInput } = UIController.elements;
        const content = typeof searchContent === 'string'
            ? searchContent
            : (searchInput ? searchInput.value.trim() : '');
        State.search = content;
        State.page = 1;
        State.selectedPaths.clear();
        this.loadFileList();
    },

    /**
     * 用途说明：加载回收站文件列表数据并触发渲染
     * 入参说明：无
     * 返回值说明：无
     */
    loadFileList() {
        const params = {
            page: State.page,
            limit: State.limit,
            sort_by: State.sortBy,
            order_asc: State.order === 'ASC',
            search: State.search
        };
        RecycleBinAPI.getList(params,
            (data) => {
                UIController.renderTable(data.list);
                // 使用公共 PageBar 组件渲染分页栏
                PageBar.init({
                    containerId: 'pagination-container',
                    totalItems: data.total,
                    pageSize: State.limit,
                    currentPage: data.page,
                    onPageChange: (newPage) => {
                        State.page = newPage;
                        this.loadFileList();
                        window.scrollTo(0, 0);
                    }
                });
            },
            (msg) => Toast.show(msg)
        );
    },

    /**
     * 用途说明：处理恢复选中文件逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleRestore() {
        const paths = Array.from(State.selectedPaths);
        UIComponents.showConfirmModal({
            title: '恢复文件',
            message: `确定要将选中的 ${paths.length} 个文件恢复到仓库吗？`,
            confirmText: '确定恢复',
            onConfirm: () => {
                RecycleBinAPI.restoreFiles(paths,
                    () => {
                        Toast.show('已恢复');
                        State.selectedPaths.clear();
                        this.loadFileList();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * 用途说明：处理彻底删除选中文件逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleDeleteSelected() {
        const paths = Array.from(State.selectedPaths);
        UIComponents.showConfirmModal({
            title: '彻底删除',
            message: `确定要彻底删除选中的 ${paths.length} 个文件吗？此操作不可恢复，将物理删除磁盘文件！`,
            confirmText: '确定删除',
            onConfirm: () => {
                RecycleBinAPI.deleteFiles(paths,
                    () => {
                        Toast.show('删除任务已启动');
                        this.startProgressPolling();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * 用途说明：处理清空回收站逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleClearAll() {
        UIComponents.showConfirmModal({
            title: '清空回收站',
            message: '确定要清空回收站中所有的文件吗？这将物理删除所有回收站内的磁盘文件！',
            confirmText: '确定清空',
            onConfirm: () => {
                RecycleBinAPI.clearAll(
                    () => {
                        Toast.show('清空任务已启动');
                        this.startProgressPolling();
                    },
                    (msg) => Toast.show(msg)
                );
            }
        });
    },

    /**
     * 用途说明：启动进度轮询，并根据状态切换逻辑决定是否刷新列表。
     * 入参说明：无
     * 返回值说明：无
     */
    startProgressPolling() {
        UIComponents.showProgressBar('.main-content', '正在删除文件...');
        // 初始化当前状态，确保能识别后续的 IDLE 切换
        State.lastTaskStatus = ProgressStatus.PROCESSING;

        const timer = setInterval(() => {
            RecycleBinAPI.getDeleteProgress(
                (data) => {
                    const currentStatus = data.status;
                    const progress = data.progress;

                    if (currentStatus === ProgressStatus.PROCESSING) {
                        UIComponents.renderProgress('.main-content', progress);
                    } else {
                        // 状态不再是 PROCESSING，停止轮询
                        clearInterval(timer);
                        UIComponents.hideProgressBar('.main-content');

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
                },
                () => {
                    clearInterval(timer);
                    UIComponents.hideProgressBar('.main-content');
                    State.lastTaskStatus = null;
                }
            );
        }, 1000);
    },

    /**
     * 用途说明：进入页面时检查是否有正在进行的删除任务
     * 入参说明：无
     * 返回值说明：无
     */
    checkTaskStatus() {
        RecycleBinAPI.getDeleteProgress(
            (data) => {
                if (data.status === ProgressStatus.PROCESSING) {
                    this.startProgressPolling();
                }
            },
            () => {}
        );
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
