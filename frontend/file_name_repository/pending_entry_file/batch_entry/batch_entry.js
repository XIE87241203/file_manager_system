/**
 * 用途说明：批量录入文件名页面的逻辑处理。
 * 包含：输入解析、利用后端批量检测接口进行对比，并跳转到结果页。
 */

// --- 状态管理 ---
const State = {
    /** @type {boolean} 是否正在进行检测 */
    isChecking: false
};

// --- UI 控制模块 ---
const UIController = {
    /** @type {Object<string, HTMLElement>} 缓存页面常用的 DOM 元素 */
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，缓存 DOM 并设置初始状态。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 初始化顶部工具栏
        UIComponents.initRepoHeader({
            title: '批量录入新数据',
            showSearch: false, // 本页面不需要搜索框
            rightBtnText: '返回列表',
            rightBtnId: 'btn-back',
            onRightBtnClick: () => {
                window.location.href = 'pending_entry_file.html';
            }
        });

        this.elements = {
            inputArea: document.getElementById('batch-input-area'),
            btnCheck: document.getElementById('btn-check-batch'),
            btnClear: document.getElementById('btn-clear-input')
        };
    }
};

// --- API 交互模块 ---
const BatchAPI = {
    /**
     * 用途说明：调用后端批量检测接口。
     * 入参说明：fileNames {string[]}: 待检测的文件名数组; showMask {boolean}: 是否显示默认遮罩。
     * 返回值说明：Promise<Object>: 包含全库检测结果的响应对象。
     */
    async checkBatch(fileNames, showMask = true) {
        return await Request.post('/api/file_name_repository/pending_entry/check_batch', { file_names: fileNames }, {}, showMask);
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：初始化应用入口。
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        UIController.init();
        this.bindEvents();
    },

    /**
     * 用途说明：绑定页面事件。
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { btnCheck, btnClear } = UIController.elements;

        btnCheck.onclick = () => this.handleCheckBatch();
        btnClear.onclick = () => this.resetPage();
    },

    /**
     * 用途说明：重置页面状态。
     * 入参说明：无
     * 返回值说明：无
     */
    resetPage() {
        /** @type {HTMLTextAreaElement} */
        const inputArea = UIController.elements.inputArea;
        inputArea.value = '';
    },

    /**
     * 用途说明：处理批量检测逻辑，检测完成后跳转到结果展示页。
     * 入参说明：无
     * 返回值说明：无
     */
    async handleCheckBatch() {
        /** @type {string} */
        const rawText = UIController.elements.inputArea.value.trim();
        if (!rawText) {
            Toast.show('请输入要检测的文件名清单~');
            return;
        }

        /** @type {string[]} */
        const inputNames = rawText.split(/[\n,，]/)
            .map(n => n.trim())
            .filter(n => n.length > 0);
        
        /** @type {string[]} */
        const uniqueNames = Array.from(new Set(inputNames));
        if (uniqueNames.length === 0) return;

        State.isChecking = true;
        const containerSelector = '.repo-content-group';
        // 使用自定义进度条，必须禁用 Request 的默认 mask
        UIComponents.showProgressBar(containerSelector, '正在全库同步校验中...');

        try {
            const response = await BatchAPI.checkBatch(uniqueNames, false);
            if (response.status === 'success') {
                // 后端现在返回的是 List[BatchCheckItemResult]，直接存储即可
                const formattedResults = response.data;
                
                // 确保数据是有效的 JSON 字符串再存入
                sessionStorage.setItem('batch_check_results', JSON.stringify(formattedResults));
                window.location.href = 'batch_check_results.html';
            } else {
                Toast.show('检测失败: ' + response.message);
            }
        } catch (error) {
            console.error('检测失败:', error);
            Toast.show('请求异常，请检查网络或后端状态');
        } finally {
            State.isChecking = false;
            UIComponents.hideProgressBar(containerSelector);
        }
    }
};

// 初始化应用
document.addEventListener('DOMContentLoaded', () => App.init());
