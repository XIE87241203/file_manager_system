/**
 * 用途说明：展示批量检测结果。
 * 已对接异步任务逻辑，支持通过返回按钮触发流程终结、清理任务并利用 history.go(-2) 解决返回冲突。
 */

// --- 状态管理 ---
const State = {
    /** @type {Object[]} 原始检测结果列表 */
    results: [],
    /** @type {boolean} 是否正在轮询进度 */
    isPolling: false,
    /** @type {number|null} 轮询定时器 ID */
    pollTimer: null
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
        UIComponents.initRepoHeader({
            title: '批量检测结果',
            showSearch: false,
            // 遵照主人指令，去除了右上角的按钮，保持界面清爽
        });

        // --- 核心逻辑：接管返回按钮并解决历史记录冲突 ---
        const backBtn = document.getElementById('nav-back-btn');
        if (backBtn) {
            backBtn.onclick = (e) => {
                // 阻止默认的 history.back()，由萌萌接管进行二次确认 and 清理
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
            selectAllCheckbox: document.getElementById('select-all-checkbox'),
            container: document.querySelector('.repo-content-group')
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
                    <input type="checkbox" class="row-checkbox" ${item.source === 'new' ? 'checked' : ''}>
                </td>
            `;

            tr.onclick = (e) => {
                if (e.target.type !== 'checkbox') {
                    const cb = tr.querySelector('.row-checkbox');
                    cb.checked = !cb.checked;
                }
                this.updateRowStyle(tr);
            };

            const checkbox = tr.querySelector('.row-checkbox');
            checkbox.onchange = () => this.updateRowStyle(tr);

            this.updateRowStyle(tr);
            tableBody.appendChild(tr);
        });

        this.elements.totalCount.textContent = results.length;
        this.elements.newCount.textContent = results.filter(r => r.source === 'new').length;
    },

    /**
     * 用途说明：更新行选中样式。
     */
    updateRowStyle(tr) {
        const checkbox = tr.querySelector('.row-checkbox');
        if (checkbox && checkbox.checked) tr.classList.add('selected-row');
        else tr.classList.remove('selected-row');
    }
};

// --- API 交互模块 ---
const ResultsAPI = {
    async getStatus() {
        return await Request.get('/api/file_name_repository/pending_entry/check_status', {}, false);
    },
    async getResults() {
        return await Request.get('/api/file_name_repository/pending_entry/check_results');
    },
    async clearTask() {
        return await Request.post('/api/file_name_repository/pending_entry/check_clear');
    },
    async confirmImport(fileNames) {
        return await Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames });
    }
};

// --- 应用逻辑主入口 ---
const App = {
    async init() {
        UIController.init();
        this.bindEvents();
        await this.loadData();
    },

    bindEvents() {
        const { btnSelectAllNew, btnConfirmImport, selectAllCheckbox } = UIController.elements;

        btnSelectAllNew.onclick = () => {
            document.querySelectorAll('#results-list-body tr').forEach(tr => {
                const isNew = tr.querySelector('.status-new');
                if (isNew) {
                    tr.querySelector('.row-checkbox').checked = true;
                    UIController.updateRowStyle(tr);
                }
            });
        };

        selectAllCheckbox.onchange = (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.row-checkbox').forEach(cb => {
                cb.checked = checked;
                UIController.updateRowStyle(cb.closest('tr'));
            });
        };

        btnConfirmImport.onclick = () => this.handleConfirmImport();
    },

    /**
     * 用途说明：数据加载与自检。
     */
    async loadData() {
        try {
            const response = await ResultsAPI.getStatus();
            if (response.status !== 'success') return;

            const { status } = response.data;
            if (status === 'completed') {
                const res = await ResultsAPI.getResults();
                if (res.status === 'success') {
                    State.results = res.data;
                    UIController.renderResults(State.results);
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

    stopPolling() {
        State.isPolling = false;
        if (State.pollTimer) {
            clearInterval(State.pollTimer);
            State.pollTimer = null;
        }
    },

    /**
     * 用途说明：处理任务终结并返回。
     * 解决冲突方案：使用 history.go(-2) 一次性退回两步，绕过输入页，完美解决返回键冲突。
     */
    handleFinishWithConfirm() {
        UIComponents.showConfirmModal({
            title: '确认返回？',
            message: '返回列表将清空本次检测结果并重置状态，确认要继续吗？',
            confirmText: '确认并返回',
            cancelText: '取消',
            onConfirm: async () => {
                // 1. 清理后端缓存
                const response = await ResultsAPI.clearTask();
                if (response.status === 'success') {
                    // 2. --- 核心：利用 history.go(-2) 实现定向“双连跳”返回 ---
                    // 逻辑说明：List -> Entry -> Results，跳过 Entry 直接回到 List，保持堆栈纯净。
                    window.history.go(-2);
                }
            }
        });
    },

    /**
     * 用途说明：执行批量录入。
     */
    async handleConfirmImport() {
        const selectedNames = [];
        document.querySelectorAll('.row-checkbox:checked').forEach(cb => {
            selectedNames.push(cb.closest('tr').dataset.name);
        });

        if (selectedNames.length === 0) {
            Toast.show('请勾选需要录入的文件名~');
            return;
        }

        try {
            const response = await ResultsAPI.confirmImport(selectedNames);
            if (response.status === 'success') {
                // 使用后端返回的实际录入数量 count
                const count = response.data?.count ?? 0;
                Toast.show(`已成功录入 ${count} 条记录！`);
            }
        } catch (e) {
            console.error('录入请求异常:', e);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
