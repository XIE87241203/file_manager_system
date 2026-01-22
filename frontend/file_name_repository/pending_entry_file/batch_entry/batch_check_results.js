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
        // 修改为通用的 initHeader，移除了搜索框，风格与设置页面保持一致
        UIComponents.initHeader('批量检测结果', true);

        // --- 核心逻辑：接管返回按钮并解决历史记录冲突 ---
        const backBtn = document.getElementById('nav-back-btn');
        if (backBtn) {
            backBtn.onclick = (e) => {
                e.preventDefault();
                App.handleFinishWithConfirm();
            };
        }

        this.elements = {
            tableBody: document.getElementById('results-list-body'),
            totalCount: document.getElementById('total-count'),
            newCount: document.getElementById('new-count'),
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
            tableBody.innerHTML = UIComponents.getEmptyTableHtml(4, '暂无检测结果');
            return;
        }

        results.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.dataset.name = item.name;

            const statusMap = {
                'index': { text: '库中已存在', class: 'status-exist' },
                'history': { text: '历史曾录入', class: 'status-history' },
                'pending': { text: '待录入库中', class: 'status-pending' },
                'new': { text: '新记录 (未收录)', class: 'status-new' }
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

        this.elements.totalCount.textContent = results.length;
        this.elements.newCount.textContent = results.filter(r => r.source === 'new').length;
        this.updateSelectedCount();
    },

    /**
     * 用途说明：刷新单行的选中 UI（样式及全局计数）。
     * 入参说明：tr (HTMLElement): 目标行；isChecked (boolean): 是否选中；shouldUpdateTotal (boolean): 是否同步刷新全局计数文案，默认为 true。
     * 返回值说明：无
     */
    refreshRowSelectionUI(tr, isChecked, shouldUpdateTotal = true) {
        if (isChecked) tr.classList.add('selected-row');
        else tr.classList.remove('selected-row');

        if (shouldUpdateTotal) {
            this.updateSelectedCount();
        }
    },

    /**
     * 用途说明：根据状态中的勾选情况更新“录入选中”按钮文案及顶部全选框。
     * 入参说明：无
     * 返回值说明：无
     */
    updateSelectedCount() {
        const selectedCount = State.results.filter(r => r.checked).length;
        const btn = this.elements.btnConfirmImport;
        const copyBtn = this.elements.btnCopySelected;

        if (btn) {
            btn.textContent = selectedCount > 0 ? `录入选中纪录 (${selectedCount})` : '录入选中纪录';
        }

        if (copyBtn) {
            copyBtn.textContent = selectedCount > 0 ? `复制选中文件名 (${selectedCount})` : '复制选中文件名';
        }

        if (this.elements.selectAllCheckbox) {
            this.elements.selectAllCheckbox.checked = selectedCount > 0 && selectedCount === State.results.length;
        }
    },

    /**
     * 用途说明：更新排序 UI，显示当前排序字段和方向。
     * 入参说明：field (string): 当前排序字段；order (string): 排序顺序 ('ASC' 或 'DESC')。
     * 返回值说明：无
     */
    updateSortUI(field, order) {
        UIComponents.updateSortUI(this.elements.sortableHeaders, field, order);
    }
};

// --- API 交互模块 ---
const ResultsAPI = {
    /**
     * 用途说明：获取当前批量检测任务的状态。
     * 返回值说明：Promise<Object>: 包含 status 和 progress 的后端响应。
     */
    async getStatus() {
        return await Request.get('/api/file_name_repository/pending_entry/check_status', {}, false);
    },
    /**
     * 用途说明：获取检测结果列表。
     * 入参说明：params (Object): 包含 sort_by (string) 和 order_asc (boolean) 的排序参数。
     * 返回值说明：Promise<Object>: 包含结果数据数组的后端响应。
     */
    async getResults(params = {}) {
        const query = new URLSearchParams(params).toString();
        return await Request.get('/api/file_name_repository/pending_entry/check_results?' + query);
    },
    /**
     * 用途说明：清理后端任务状态及缓存。
     * 返回值说明：Promise<Object>: 操作结果状态。
     */
    async clearTask() {
        return await Request.post('/api/file_name_repository/pending_entry/check_clear');
    },
    /**
     * 用途说明：确认录入选中的文件名。
     * 入参说明：fileNames (string[]): 待录入的文件名数组。
     * 返回值说明：Promise<Object>: 包含成功录入的数量。
     */
    async confirmImport(fileNames) {
        return await Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames });
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用。
     * 返回值说明：无
     */
    async init() {
        UIController.init();
        this.bindEvents();
        await this.loadData();
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
    async loadData() {
        try {
            const response = await ResultsAPI.getStatus();
            if (response.status !== 'success') return;

            const { status } = response.data;
            if (status === 'completed') {
                const params = {
                    sort_by: State.sortBy,
                    order_asc: State.order === 'ASC'
                };
                const res = await ResultsAPI.getResults(params);
                if (res.status === 'success') {
                    State.results = res.data.map(item => ({
                        ...item,
                        checked: item.source === 'new'
                    }));
                    UIController.renderResults(State.results);
                    UIController.updateSortUI(State.sortBy, State.order);
                }
            } else if (status === 'processing') {
                this.startPolling();
            } else if (status === 'idle') {
                Toast.show('任务已结束');
                setTimeout(() => { window.history.back(); }, 1000);
            }
        } catch (e) {
            console.error('加载异常:', e);
        }
    },

    /**
     * 用途说明：启动进度轮询。
     * 返回值说明：无
     */
    startPolling() {
        if (State.isPolling) return;
        State.isPolling = true;
        UIComponents.showProgressBar('.repo-content-group', '正在同步进度...');

        State.pollTimer = setInterval(async () => {
            const response = await ResultsAPI.getStatus();
            if (response.status !== 'success') return;

            const { status, progress } = response.data;
            if (status === 'processing') {
                const percent = progress.total > 0 ? Math.floor((progress.current / progress.total) * 100) : 0;
                UIComponents.updateProgressBar('.repo-content-group', percent, progress.message);
            } else if (status === 'completed') {
                this.stopPolling();
                UIComponents.hideProgressBar('.repo-content-group');
                this.loadData();
            }
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
            title: '确认返回？',
            message: '返回列表将清空本次检测结果并重置状态，确认要继续吗？',
            confirmText: '确认并返回',
            cancelText: '取消',
            onConfirm: async () => {
                const response = await ResultsAPI.clearTask();
                if (response.status === 'success') {
                    window.history.go(-2);
                }
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
            Toast.show('请勾选需要复制的文件名~');
            return;
        }

        const textToCopy = selectedNames.join('\n');
        navigator.clipboard.writeText(textToCopy).then(() => {
            Toast.show(`已成功复制 ${selectedNames.length} 条文件名到剪贴板`);
        }).catch(err => {
            console.error('复制失败:', err);
            Toast.show('复制失败，请重试');
        });
    },

    /**
     * 用途说明：执行批量录入，直接从状态中筛选选中的项。
     * 返回值说明：无
     */
    async handleConfirmImport() {
        const selectedNames = State.results
            .filter(item => item.checked)
            .map(item => item.name);

        if (selectedNames.length === 0) {
            Toast.show('请勾选需要录入的文件名~');
            return;
        }

        try {
            const response = await ResultsAPI.confirmImport(selectedNames);
            if (response.status === 'success') {
                const count = response.data?.count ?? 0;
                Toast.show(`已成功录入 ${count} 条记录！`);
                if(count>0){
                    await this.loadData();
                }

            }
        } catch (e) {
            console.error('录入请求异常:', e);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
