/**
 * 用途说明：展示批量检测结果。
 * 已对接异步任务逻辑，支持通过返回按钮触发流程终结、清理任务并利用 history.go(-2) 解决返回冲突。
 */

// --- 状态管理 ---
const State = {
    /** @type {Object[]} 原始检测结果列表，每个项扩展包含 {name: string, source: string, detail: string, checked: boolean} */
    results: [],
    /** @type {boolean} 是否正在轮询进度 */
    isPolling: false,
    /** @type {number|null} 轮询定时器 ID */
    pollTimer: null,
    /** @type {string|null} 当前排序字段 */
    sortBy: null,
    /** @type {string} 排序顺序，'ASC' 或 'DESC' */
    order: 'DESC'
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 布局，设置头部并接管返回按钮逻辑。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用 HeaderToolbar 初始化顶部工具栏
        HeaderToolbar.init({
            title: I18nManager.t('batch_check.page_title'),
            showBack: true,
            backCallback: () => {
                App.handleFinishWithConfirm();
            }
        });

        this.elements = {
            tableBody: document.getElementById('results-list-body'),
            statContainer: document.getElementById('stat-info-container'),
            btnSelectAllNew: document.getElementById('btn-select-all-new'),
            btnConfirmImport: document.getElementById('btn-confirm-import'),
            btnCopySelected: document.getElementById('btn-copy-selected'),
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            container: document.querySelector('.repo-content-group'),
            /** @type {NodeListOf<HTMLElement>} 所有可排序的表头 */
            sortableHeaders: document.querySelectorAll('th.sortable')
        };
    },

    /**
     * 用途说明：渲染检测结果。
     * 入参说明：results (Object[]): 结果数据列表。
     * 返回值说明：无
     */
    renderResults(results) {
        const { tableBody } = this.elements;
        tableBody.innerHTML = '';

        if (!results || results.length === 0) {
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, I18nManager.t('batch_check.empty_results'));
            return;
        }

        results.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.dataset.name = item.name;

            const statusMap = {
                'index': { text: I18nManager.t('batch_check.status_index'), class: 'status-exist' },
                'history': { text: I18nManager.t('batch_check.status_history'), class: 'status-history' },
                'pending': { text: I18nManager.t('batch_check.status_pending'), class: 'status-pending' },
                'new': { text: I18nManager.t('batch_check.status_new'), class: 'status-new' }
            };
            const statusInfo = statusMap[item.source] || { text: item.source, class: '' };

            tr.innerHTML = `
                <td class="col-index">${index + 1}</td>
                <td class="col-name">${item.name}</td>
                <td class="col-status">
                    <div class="status-badge ${statusInfo.class}">${statusInfo.text}</div>
                    <div class="status-detail">${item.detail || ''}</div>
                </td>
                <td class="col-check">
                    <input type="checkbox" class="row-checkbox" ${item.checked ? 'checked' : ''}>
                </td>
            `;

            tr.onclick = (e) => {
                const checkbox = tr.querySelector('.row-checkbox');
                if (e.target.type !== 'checkbox') {
                    item.checked = !item.checked;
                    checkbox.checked = item.checked;
                } else {
                    item.checked = e.target.checked;
                }
                this.refreshRowSelectionUI(tr, item.checked);
            };

            this.refreshRowSelectionUI(tr, item.checked, false);
            tableBody.appendChild(tr);
        });

        // 渲染统计文案
        if (this.elements.statContainer) {
            this.elements.statContainer.innerHTML = I18nManager.t('batch_check.stat_info', {
                total: results.length,
                new: results.filter(r => r.source === 'new').length
            });
        }

        this.updateSelectedCount();
    },

    /**
     * 用途说明：刷新单行的选中 UI（样式及全局计数）。
     * @param {HTMLElement} tr - 入参说明：目标行元素
     * @param {boolean} isChecked - 入参说明：是否选中
     * @param {boolean} shouldUpdateTotal - 入参说明：是否同步刷新全局计数文案，默认为 true
     * @returns {void} - 返回值说明：无
     */
    refreshRowSelectionUI(tr, isChecked, shouldUpdateTotal = true) {
        if (isChecked) tr.classList.add('selected-row');
        else tr.classList.remove('selected-row');

        if (shouldUpdateTotal) {
            this.updateSelectedCount();
        }
    },

    /**
     * 用途说明：根据状态中的勾选情况更新底部操作按钮文案、显隐状态及顶部全选框。
     * 入参说明：无
     * 返回值说明：无
     */
    updateSelectedCount() {
        const selectedCount = State.results.filter(r => r.checked).length;
        const btn = this.elements.btnConfirmImport;
        const copyBtn = this.elements.btnCopySelected;

        // 处理“确认录入”按钮文案与显隐
        if (btn) {
            if (selectedCount > 0) {
                btn.classList.remove('hidden');
                btn.innerText = I18nManager.t('batch_check.confirm_import_count', { count: selectedCount });
            } else {
                btn.classList.add('hidden');
            }
        }

        // 处理“复制选中”按钮文案与显隐
        if (copyBtn) {
            if (selectedCount > 0) {
                copyBtn.classList.remove('hidden');
                 copyBtn.innerText = I18nManager.t('batch_check.copy_selected_count', { count: selectedCount });
            } else {
                copyBtn.classList.add('hidden');
            }
        }

        if (this.elements.selectAllCheckbox) {
            this.elements.selectAllCheckbox.checked = selectedCount > 0 && selectedCount === State.results.length;
        }
    },

    /**
     * 用途说明：更新排序 UI，显示当前排序字段和方向。
     * @param {string} field - 入参说明：当前排序字段
     * @param {string} order - 入参说明：排序顺序 ('ASC' 或 'DESC')
     * @returns {void} - 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用。
     * 返回值说明：无
     */
    init() {
        // 初始化多语言
        I18nManager.init();
        I18nManager.render();

        UIController.init();
        this.bindEvents();
        this.loadData();
    },

    /**
     * 用途说明：绑定页面事件逻辑。
     * 返回值说明：无
     */
    bindEvents() {
        const { btnSelectAllNew, btnConfirmImport, btnCopySelected, selectAllCheckbox, sortableHeaders } = UIController.elements;

        // 全选所有“新记录”
        btnSelectAllNew.onclick = () => {
            State.results.forEach(item => {
                if (item.source === 'new') {
                    item.checked = true;
                }
            });
            UIController.renderResults(State.results);
        };

        // 顶部全选/取消全选
        selectAllCheckbox.onchange = (e) => {
            const checked = e.target.checked;
            State.results.forEach(item => {
                item.checked = checked;
            });
            UIController.renderResults(State.results);
        };

        btnConfirmImport.onclick = () => this.handleConfirmImport();

        // 复制选中文件名到剪贴板
        if (btnCopySelected) {
            btnCopySelected.onclick = () => this.handleCopySelectedNames();
        }

        // 绑定排序事件
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
                this.loadData();
            };
        });
    },

    /**
     * 用途说明：加载数据并根据后端状态驱动 UI（轮询或渲染）。
     * 返回值说明：无
     */
    loadData() {
        BatchCheckResultsRequest.getStatus((data) => {
            const { status } = data;
            if (status === 'completed') {
                const params = {
                    sort_by: State.sortBy,
                    order_asc: State.order === 'ASC'
                };
                BatchCheckResultsRequest.getResults(params, (resultsData) => {
                    State.results = resultsData.map(item => ({
                        ...item,
                        checked: item.source === 'new'
                    }));
                    UIController.renderResults(State.results);
                    UIController.updateSortUI(State.sortBy, State.order);
                }, (err) => Toast.show(err));
            } else if (status === 'processing') {
                this.startPolling();
            } else if (status === 'idle') {
                Toast.show(I18nManager.t('batch_check.task_finished'));
                setTimeout(() => { window.history.back(); }, 1000);
            }
        }, (err) => {
            console.error(I18nManager.t('batch_check.get_status_failed'), err);
        });
    },

    /**
     * 用途说明：启动进度轮询。
     * 返回值说明：无
     */
    startPolling() {
        if (State.isPolling) return;
        State.isPolling = true;
        UIComponents.showProgressBar('.repo-content-group', I18nManager.t('batch_check.sync_progress'));

        State.pollTimer = setInterval(() => {
            BatchCheckResultsRequest.getStatus((data) => {
                const { status, progress } = data;
                if (status === 'processing') {
                    const percent = progress.total > 0 ? Math.floor((progress.current / progress.total) * 100) : 0;
                    UIComponents.updateProgressBar('.repo-content-group', percent, progress.message);
                } else if (status === 'completed') {
                    this.stopPolling();
                    UIComponents.hideProgressBar('.repo-content-group');
                    this.loadData();
                }
            }, (err) => {
                console.error(I18nManager.t('batch_check.get_status_failed'), err);
            });
        }, 1000);
    },

    /**
     * 用途说明：停止轮询。
     * 返回值说明：无
     */
    stopPolling() {
        State.isPolling = false;
        if (State.pollTimer) {
            clearInterval(State.pollTimer);
            State.pollTimer = null;
        }
    },

    /**
     * 用途说明：处理返回逻辑，确认并清理后端任务。
     * 返回值说明：无
     */
    handleFinishWithConfirm() {
        UIComponents.showConfirmModal({
            title: I18nManager.t('batch_check.back_confirm_title'),
            message: I18nManager.t('batch_check.back_confirm_msg'),
            confirmText: I18nManager.t('batch_check.back_confirm_ok'),
            cancelText: I18nManager.t('common.cancel'),
            onConfirm: () => {
                BatchCheckResultsRequest.clearTask(() => {
                    window.history.go(-2);
                }, (err) => Toast.show(err));
            }
        });
    },

    /**
     * 用途说明：复制选中的文件名到剪贴板。
     * 返回值说明：无
     */
    handleCopySelectedNames() {
        const selectedNames = State.results
            .filter(item => item.checked)
            .map(item => item.name);

        if (selectedNames.length === 0) {
            Toast.show(I18nManager.t('batch_check.copy_hint'));
            return;
        }

        const textToCopy = selectedNames.join('\n');
        navigator.clipboard.writeText(textToCopy).then(() => {
            Toast.show(I18nManager.t('batch_check.copy_success', { count: selectedNames.length }));
        }).catch(err => {
            console.error(I18nManager.t('batch_check.copy_failed'), err);
            Toast.show(I18nManager.t('batch_check.copy_failed'));
        });
    },

    /**
     * 用途说明：执行批量录入，直接从状态中筛选选中的项。
     * 返回值说明：无
     */
    handleConfirmImport() {
        const selectedNames = State.results
            .filter(item => item.checked)
            .map(item => item.name);

        if (selectedNames.length === 0) {
            Toast.show(I18nManager.t('batch_check.import_hint'));
            return;
        }

        BatchCheckResultsRequest.confirmImport(selectedNames, (data) => {
            const count = data?.count ?? 0;
            Toast.show(I18nManager.t('batch_check.import_success', { count: count }));
            if (count > 0) {
                this.loadData();
            }
        }, (err) => {
            Toast.show(err);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
