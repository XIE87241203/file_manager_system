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
    /** @type {Object} 缓存的 DOM 元素集合 */
    elements: {},

    /**
     * 用途说明：初始化 UI 组件并缓存 DOM 元素。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 使用标准的 HeaderToolbar 组件初始化头部
        HeaderToolbar.init({
            title: '批量录入文件名',
            showBack: true
        });

        this.elements = {
            inputArea: document.getElementById('batch-input-area'),
            btnCheck: document.getElementById('btn-check-batch'),
            btnClear: document.getElementById('btn-clear-input'),
            container: document.querySelector('.repo-content-group')
        };
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：页面逻辑初始化入口。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
        // 入口守卫：根据后端状态决定行为（如断点续传或自动跳转）
        this.guardEntry();
    },

    /**
     * 用途说明：绑定页面按钮及其他交互事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { btnCheck, btnClear } = UIController.elements;
        btnCheck.onclick = () => this.handleCheckBatch();
        btnClear.onclick = () => { UIController.elements.inputArea.value = ''; };
    },

    /**
     * 用途说明：入口守卫。检查是否有正在进行的任务，并据此决定是否启动轮询或直接跳转。
     * 入参说明：无
     * 返回值说明：无
     */
    guardEntry() {
        BatchEntryRequest.getStatus(
            (data) => {
                const { status } = data;
                if (status === 'processing') {
                    this.startPolling();
                } else if (status === 'completed') {
                    // 任务已完成，跳转到结果展示页
                    window.location.href = 'batch_check_results.html';
                }
            },
            (errorMessage) => {
                console.error('自检异常:', errorMessage);
            }
        );
    },

    /**
     * 用途说明：处理“开始检测”按钮点击事件，解析输入并启动后端任务。
     * 入参说明：无
     * 返回值说明：无
     */
    handleCheckBatch() {
        /** @type {string} 获取并清理输入文本 */
        const rawText = UIController.elements.inputArea.value.trim();
        if (!rawText) {
            Toast.show('请输入要检测的文件名清单~');
            return;
        }

        // 解析输入，支持换行和逗号
        /** @type {string[]} */
        const inputNames = rawText.split(/[\n,，]/).map(n => n.trim()).filter(n => n.length > 0);
        /** @type {string[]} 去重 */
        const uniqueNames = Array.from(new Set(inputNames));
        if (uniqueNames.length === 0) return;

        BatchEntryRequest.startCheck(uniqueNames,
            () => { // onSuccess
                this.startPolling();
            },
            (errorMessage) => { // onError
                Toast.show(errorMessage || '启动失败');
                console.error('请求失败:', errorMessage);
            }
        );
    },

    /**
     * 用途说明：启动进度轮询，实时展示检测进度条。
     * 入参说明：无
     * 返回值说明：无
     */
    startPolling() {
        if (State.isChecking) return;
        State.isChecking = true;

        UIComponents.showProgressBar('.repo-content-group', '正在检测中...');

        State.pollTimer = setInterval(() => {
            BatchEntryRequest.getStatus(
                (data) => { // onSuccess
                    const { status, progress } = data;
                    if (status === 'processing') {
                        const percent = progress.total > 0 ? Math.floor((progress.current / progress.total) * 100) : 0;
                        UIComponents.updateProgressBar('.repo-content-group', percent, progress.message);
                    } else if (status === 'completed') {
                        this.stopPolling();
                        UIComponents.hideProgressBar('.repo-content-group');
                        window.location.href = 'batch_check_results.html';
                    } else if (status === 'error') {
                        this.stopPolling();
                        UIComponents.hideProgressBar('.repo-content-group');
                        Toast.show('运行出错: ' + progress.message);
                    }
                },
                (errorMessage) => { // onError
                    console.error('轮询异常:', errorMessage);
                    this.stopPolling();
                    UIComponents.hideProgressBar('.repo-content-group');
                    Toast.show('轮询任务状态时出错: ' + errorMessage);
                }
            );
        }, 1000);
    },

    /**
     * 用途说明：停止进度轮询并清理定时器。
     * 入参说明：无
     * 返回值说明：无
     */
    stopPolling() {
        State.isChecking = false;
        if (State.pollTimer) {
            clearInterval(State.pollTimer);
            State.pollTimer = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
