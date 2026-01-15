/**
 * 用途说明：批量录入文件名页面的逻辑处理。
 * 包含：输入解析、利用后端批量检测接口进行对比展示、以及确认录入。
 */

/**
 * @typedef {Object} ExistItem
 * @property {string} name - 文件名
 * @property {string} source - 来源库 (index/history/pending)
 * @property {string} detail - 详细路径或说明
 */

// --- 状态管理 ---
const State = {
    /** @type {string[]} 存储待录入的新记录文件名数组 */
    newList: [], 
    /** @type {ExistItem[]} 存储已存在的记录详情数组 */
    existsList: [], 
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
            btnClear: document.getElementById('btn-clear-input'),
            btnConfirm: document.getElementById('btn-confirm-save'),
            resultsSection: document.getElementById('check-results-section'),
            existsListBody: document.getElementById('exists-list-body'),
            newListBody: document.getElementById('new-list-body'),
            countExists: document.getElementById('count-exists'),
            countNew: document.getElementById('count-new')
        };
    },

    /**
     * 用途说明：渲染检测结果表格。
     * 入参说明：无
     * 返回值说明：无
     */
    renderResults() {
        /** @type {HTMLElement} */
        const { existsListBody, newListBody, countExists, countNew, btnConfirm, resultsSection } = this.elements;
        
        resultsSection.classList.remove('hidden');
        existsListBody.innerHTML = '';
        newListBody.innerHTML = '';

        // 渲染已存在项
        State.existsList.forEach(item => {
            const tr = document.createElement('tr');
            tr.className = 'row-exist-item';
            
            let statusTag = '';
            
            if (item.source === 'index') {
                statusTag = '<span class="status-tag tag-index">索引库已存在</span>';
            } else if (item.source === 'history') {
                statusTag = '<span class="status-tag tag-history">曾录入库已存在</span>';
            } else if (item.source === 'pending') {
                statusTag = '<span class="status-tag tag-pending">待录入库已存在</span>';
            }

            tr.innerHTML = `
                <td class="col-name">${item.name}</td>
                <td class="col-path">${statusTag} <small>${item.detail || ''}</small></td>
            `;
            existsListBody.appendChild(tr);
        });

        // 渲染新记录项
        State.newList.forEach(name => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="col-name">${name}</td>`;
            newListBody.appendChild(tr);
        });

        countExists.textContent = State.existsList.length.toString();
        countNew.textContent = State.newList.length.toString();

        // 只有存在新记录时才显示确认按钮
        if (State.newList.length > 0) {
            btnConfirm.classList.remove('hidden');
            btnConfirm.textContent = `确认录入这 ${State.newList.length} 条记录`;
        } else {
            btnConfirm.classList.add('hidden');
        }
    }
};

// --- API 交互模块 ---
const BatchAPI = {
    /**
     * 用途说明：调用后端批量检测接口。
     * 入参说明：fileNames {string[]}: 待检测的文件名数组。
     * 返回值说明：Promise<Object>: 包含全库检测结果的响应对象。
     */
    async checkBatch(fileNames) {
        return await Request.post('/api/file_name_repository/pending_entry/check_batch', { file_names: fileNames });
    },

    /**
     * 用途说明：批量录入新文件名。
     * 入参说明：fileNames {string[]}: 文件名数组。
     * 返回值说明：Promise<Object>: 包含操作结果的响应对象。
     */
    async saveToPendingRepo(fileNames) {
        return await Request.post('/api/file_name_repository/pending_entry/add', { file_names: fileNames });
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
        const { btnCheck, btnClear, btnConfirm } = UIController.elements;

        btnCheck.onclick = () => this.handleCheckBatch();
        btnClear.onclick = () => this.resetPage();
        btnConfirm.onclick = () => this.handleConfirmSave();
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
        UIController.elements.resultsSection.classList.add('hidden');
        State.newList = [];
        State.existsList = [];
    },

    /**
     * 用途说明：处理批量检测逻辑。
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
        UIComponents.showProgressBar(containerSelector, '正在全库同步校验中...');

        try {
            const response = await BatchAPI.checkBatch(uniqueNames);
            if (response.status === 'success') {
                const results = response.data;
                State.existsList = [];
                State.newList = [];

                // 解析后端返回的聚合结果
                uniqueNames.forEach(name => {
                    const res = results[name];
                    if (!res || res.source === 'new') {
                        State.newList.push(name);
                    } else {
                        State.existsList.push({
                            name: name,
                            source: res.source,
                            detail: res.detail
                        });
                    }
                });

                UIController.renderResults();
                Toast.show(`检测完成！发现 ${State.newList.length} 条新记录。`);
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
    },

    /**
     * 用途说明：处理确认录入逻辑。
     * 入参说明：无
     * 返回值说明：无
     */
    handleConfirmSave() {
        if (State.newList.length === 0) return;

        UIComponents.showConfirmModal({
            title: '确认录入',
            message: `确定要将这 ${State.newList.length} 条新记录存入“待录入文件名库”吗？`,
            confirmText: '确认录入',
            onConfirm: async () => {
                const containerSelector = '.repo-content-group';
                UIComponents.showProgressBar(containerSelector, '正在为您录入新数据...');
                try {
                    const response = await BatchAPI.saveToPendingRepo(State.newList);
                    if (response.status === 'success') {
                        Toast.show('录入成功！');
                        // 成功后重置页面状态，保持在当前页面
                        this.resetPage();
                    } else {
                        Toast.show('录入失败: ' + response.message);
                    }
                } finally {
                    UIComponents.hideProgressBar(containerSelector);
                }
            }
        });
    }
};

// 初始化应用
document.addEventListener('DOMContentLoaded', () => App.init());
