/**
 * 用途说明：批量录入文件名页面的逻辑处理。
 * 支持异步任务自动检测分流，尊重原生历史堆栈逻辑。
 */

// --- 状态管理 ---
const State = {
    /** @type {boolean} 是否正在进行检测 */
    isChecking: false,
    /** @type {number|null} 轮询定时器 ID */
    pollTimer: null
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 并缓存元素。
     */
    init() {
        UIComponents.initRepoHeader({
            title: '批量录入新数据',
            showSearch: false,
        });

        this.elements = {
            inputArea: document.getElementById('batch-input-area'),
            btnCheck: document.getElementById('btn-check-batch'),
            btnClear: document.getElementById('btn-clear-input'),
            container: document.querySelector('.repo-content-group')
        };
    }
};

// --- API 交互模块 ---
const BatchAPI = {
    async startCheck(fileNames) {
        return await Request.post('/api/file_name_repository/pending_entry/check_batch', { file_names: fileNames }, {}, false);
    },
    async getStatus() {
        return await Request.get('/api/file_name_repository/pending_entry/check_status', {}, false);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    init() {
        UIController.init();
        this.bindEvents();
        // 入口守卫：根据后端状态决定行为
        this.guardEntry();
    },

    bindEvents() {
        const { btnCheck, btnClear } = UIController.elements;
        btnCheck.onclick = () => this.handleCheckBatch();
        btnClear.onclick = () => { UIController.elements.inputArea.value = ''; };
    },

    /**
     * 用途说明：入口守卫。
     * 逻辑说明：使用 location.href 进行正常跳转，确保返回键能回到本页并触发逻辑。
     */
    async guardEntry() {
        try {
            const response = await BatchAPI.getStatus();
            if (response.status !== 'success') return;

            const { status } = response.data;
            if (status === 'processing') {
                this.startPolling();
            } else if (status === 'completed') {
                // 任务已完成，正常跳转，保留历史记录
                window.location.href = 'batch_check_results.html';
            }
        } catch (e) {
            console.error('自检异常:', e);
        }
    },

    /**
     * 用途说明：启动批量检测。
     */
    async handleCheckBatch() {
        const rawText = UIController.elements.inputArea.value.trim();
        if (!rawText) {
            Toast.show('请输入要检测的文件名清单~');
            return;
        }

        const inputNames = rawText.split(/[\n,，]/).map(n => n.trim()).filter(n => n.length > 0);
        const uniqueNames = Array.from(new Set(inputNames));
        if (uniqueNames.length === 0) return;

        try {
            const response = await BatchAPI.startCheck(uniqueNames);
            if (response.status === 'success') {
                this.startPolling();
            } else {
                Toast.show(response.message || '启动失败');
            }
        } catch (error) {
            console.error('请求失败:', error);
        }
    },

    /**
     * 用途说明：进度轮询。
     */
    startPolling() {
        if (State.isChecking) return;
        State.isChecking = true;

        UIComponents.showProgressBar('.repo-content-group', '正在检测中...');

        State.pollTimer = setInterval(async () => {
            try {
                const response = await BatchAPI.getStatus();
                if (response.status !== 'success') return;

                const { status, progress } = response.data;
                if (status === 'processing') {
                    const percent = progress.total > 0 ? Math.floor((progress.current / progress.total) * 100) : 0;
                    UIComponents.updateProgressBar('.repo-content-group', percent, progress.message);
                } else if (status === 'completed') {
                    this.stopPolling();
                    UIComponents.hideProgressBar('.repo-content-group');
                    // 完成后正常跳转
                    window.location.href = 'batch_check_results.html';
                } else if (status === 'error') {
                    this.stopPolling();
                    UIComponents.hideProgressBar('.repo-content-group');
                    Toast.show('运行出错: ' + progress.message);
                }
            } catch (e) {
                console.error('轮询异常:', e);
            }
        }, 1000);
    },

    stopPolling() {
        State.isChecking = false;
        if (State.pollTimer) {
            clearInterval(State.pollTimer);
            State.pollTimer = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
