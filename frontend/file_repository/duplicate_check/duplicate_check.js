/**
 * 用途说明：查重页面 logic 处理，负责触发查重任务、进度监控以及查重结果的分页展示与交互。
 */

// --- 状态管理 ---
const CheckState = {
    results: [],
    page: 1,
    limit: 20,
    total: 0,
    similarityType: '', // 存储当前的筛选类型
    lastCheckTime: '--',
    pollingInterval: null,
    settings: null, // 存储系统设置
    paginationController: null, // 分页控制器实例
    previousExpandedStates: null, // 用途说明：存储上一页结果的展开/收起状态，用于刷新后保留状态
    selectedPaths: new Set(), // 存储选中的文件路径，以保持跨页选中状态

    /**
     * 用途说明：更新结果列表及分页信息
     * 入参说明：data (Object) - 后端返回的 PaginationResult 结构
     * 入参说明：expandedStatesMap (Object|null) - 存储分组ID到isExpanded状态的映射，用于恢复分组的展开状态
     * 返回值说明：无
     */
    setPaginationData(data, expandedStatesMap = null) {
        this.results = data.list || [];
        this.total = data.total || 0;
        this.page = data.page || 1;
        this.limit = data.limit || 20;

        // 恢复分组的展开状态
        this.results.forEach(group => {
            if (expandedStatesMap && expandedStatesMap[group.id] !== undefined) {
                group.isExpanded = expandedStatesMap[group.id];
            } else {
                // 默认为展开状态
                group.isExpanded = true;
            }
        });

        this.lastCheckTime = UIComponents.formatDate();
    }
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * 用途说明：初始化 UI 控制器，缓存常用的 DOM 元素
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        this.elements = {
            wrapper: document.getElementById('results-wrapper'),
            scanningContainer: document.getElementById('scanning-container'),
            resultsGroup: document.getElementById('results-group'),
            emptyHint: document.getElementById('empty-hint'),
            summaryBar: document.getElementById('results-summary-bar'),
            summaryGroups: document.getElementById('summary-groups'),
            summaryFiles: document.getElementById('summary-files'),
            summaryTime: document.getElementById('summary-time'),
            globalDeleteBtn: document.getElementById('btn-delete-selected-global'),
            filterSimilarityType: document.getElementById('filter-similarity-type')
        };

        // 初始化公用分页组件
        CheckState.paginationController = UIComponents.initPagination('pagination-container', {
            limit: CheckState.limit,
            onPageChange: (newPage) => App.changePage(newPage)
        });

        // 绑定全局删除按钮
        this.elements.globalDeleteBtn.onclick = () => {
            const paths = Array.from(CheckState.selectedPaths);
            if (paths.length > 0) {
                App.moveToRecycleBin(paths, `确定要将选中的 ${paths.length} 个文件移入回收站吗？\n(移入回收站后若组内文件少于2个，该组将自动解散)`);
            }
        };

        // 绑定筛选事件
        if (this.elements.filterSimilarityType) {
            this.elements.filterSimilarityType.onchange = () => {
                CheckState.similarityType = this.elements.filterSimilarityType.value;
                App.loadResults(1);
            };
        }

        this.renderHeader(ProgressStatus.IDLE);
    },

    /**
     * 用途说明：渲染顶部导航栏，根据任务状态切换“开始”与“停止”按钮
     * 入参说明：status (String) - ProgressStatus 枚举值
     * 返回值说明：无
     */
    renderHeader(status) {
        if (typeof UIComponents !== 'undefined') {
            const title = '文件查重';
            if (status === ProgressStatus.PROCESSING) {
                UIComponents.initHeader(title, true, null, '停止查重', () => DuplicateCheckAPI.stop(), 'btn-text-danger');
            } else {
                UIComponents.initHeader(title, true, null, '开始查重', () => DuplicateCheckAPI.start());
            }
        }
    },

    /**
     * 用途说明：切换页面视图状态（查重中、显示结果、显示初始引导）
     * 入参说明：status (String) - 任务状态（ProgressStatus 枚举值）
     * 返回值说明：无
     */
    toggleView(status) {
        const { scanningContainer, resultsGroup, emptyHint } = this.elements;
        if (status === ProgressStatus.PROCESSING) {
            this.renderHeader(ProgressStatus.PROCESSING);
            scanningContainer.classList.remove('hidden');
            resultsGroup.classList.add('hidden');
            emptyHint.classList.add('hidden');
            UIComponents.showProgressBar('#scanning-container', '正在准备分析文件...');
        } else {
            this.renderHeader(ProgressStatus.IDLE);
            scanningContainer.classList.add('hidden');
            UIComponents.hideProgressBar('#scanning-container');

            if (status === ProgressStatus.COMPLETED || (CheckState.results && CheckState.results.length > 0) || CheckState.similarityType !== '') {
                resultsGroup.classList.remove('hidden');
                emptyHint.classList.add('hidden');
            } else {
                resultsGroup.classList.add('hidden');
                if (status === ProgressStatus.IDLE) {
                    emptyHint.classList.remove('hidden');
                } else {
                    emptyHint.classList.add('hidden');
                }
            }
        }
    },

    /**
     * 用途说明：更新扫描进度条及状态文字
     * 入参说明：progress (Object) - 进度数据
     * 返回值说明：无
     */
    updateProgress(progress) {
        UIComponents.renderProgress('#scanning-container', progress);
    },

    /**
     * 用途说明：全量渲染查重结果列表及统计栏
     * 入参说明：无
     * 返回值说明：无
     */
    renderResults() {
        const { wrapper, summaryBar, summaryGroups, summaryFiles, summaryTime } = this.elements;
        wrapper.innerHTML = '';

        const results = CheckState.results;
        if (!results || results.length === 0) {
            summaryBar.classList.remove('hidden');
            wrapper.innerHTML = '<div style="text-align: center; color: #9aa0a6; padding-top: 100px;">未发现重复文件</div>';
            if (CheckState.paginationController) CheckState.paginationController.update(0, 1);
            this.updateFloatingBar();
            return;
        }

        summaryBar.classList.remove('hidden');
        summaryGroups.textContent = `重复组总数: ${CheckState.total}`;
        const totalFiles = results.reduce((acc, g) => acc + (g.files ? g.files.length : 0), 0);
        summaryFiles.textContent = `当前页文件: ${totalFiles}`;
        summaryTime.textContent = `刷新时间: ${CheckState.lastCheckTime}`;

        results.forEach(group => {
            const groupEl = this.createGroupElement(group);
            wrapper.appendChild(groupEl);
        });

        // 更新公用分页组件
        if (CheckState.paginationController) {
            CheckState.paginationController.update(CheckState.total, CheckState.page);
        }

        this.updateFloatingBar();
    },

    /**
     * 用途说明：创建一个重复分组的 DOM 元素
     * 入参说明：group (Object) - 分组数据 (DuplicateGroupResult)
     * 返回值说明：HTMLElement - 分组节点
     */
    createGroupElement(group) {
        const groupEl = document.createElement('div');
        groupEl.className = `duplicate-group ${group.isExpanded ? 'expanded' : ''}`;
        groupEl.setAttribute('data-group-id', group.id);

        const files = group.files || [];
        const fileCount = files.length;
        const groupType = group.group_name || '重复组';

        groupEl.innerHTML = `
            <div class="group-header">
                <div class="group-info">
                    <span class="group-title">${groupType}</span>
                    <span class="group-count">${fileCount} 个文件</span>
                    <span class="group-md5">ID: ${group.id}</span>
                </div>
                <div class="group-actions">
                    <span class="expand-icon">▶</span>
                </div>
            </div>
            <div class="group-content">
                <table class="file-item-table">
                    <thead>
                        <tr class="header-row-clickable">
                            <th class="col-dup-name">文件名</th>
                            <th class="col-dup-similarity">相似率</th>
                            <th class="col-dup-size">大小</th>
                            <th class="col-dup-path">完整路径</th>
                            <th class="col-dup-check">
                                <input type="checkbox" class="file-checkbox select-all-in-group">
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        ${files.map(f => {
                            const info = f.file_info;
                            const isChecked = CheckState.selectedPaths.has(info.file_path);
                            const fileName = UIComponents.getFileName(info.file_path);
                            const fileSizeStr = CommonUtils.formatFileSize(info.file_size);
                            
                            // 格式化相似率：类型(百分比)
                            const typeMap = {
                                'md5': 'MD5',
                                'hash': '图片指纹',
                                'video_feature': '视频指纹'
                            };
                            const typeStr = typeMap[f.similarity_type] || f.similarity_type;
                            const rateStr = (f.similarity_rate * 100).toFixed(1) + '%';
                            const similarityDisplay = `${typeStr}(${rateStr})`;

                            return `
                                <tr class="clickable-row ${isChecked ? 'selected-row' : ''}" data-path="${info.file_path}" data-thumbnail="${info.thumbnail_path || ''}">
                                    <td class="col-dup-name" title="${fileName}">${fileName}</td>
                                    <td class="col-dup-similarity">${similarityDisplay}</td>
                                    <td class="col-dup-size">${fileSizeStr}</td>
                                    <td class="col-dup-path file-path" title="${info.file_path}">${info.file_path}</td>
                                    <td class="col-dup-check">
                                        <input type="checkbox" class="file-checkbox file-item-checkbox" data-path="${info.file_path}" ${isChecked ? 'checked' : ''}>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;

        const header = groupEl.querySelector('.group-header');
        header.addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            groupEl.classList.toggle('expanded');
            const groupId = groupEl.getAttribute('data-group-id');
            const targetGroup = CheckState.results.find(g => String(g.id) === groupId);
            if (targetGroup) {
                targetGroup.isExpanded = groupEl.classList.contains('expanded');
            }
        });

        const tbody = groupEl.querySelector('tbody');
        const selectAllInGroup = groupEl.querySelector('.select-all-in-group');
        const theadRow = groupEl.querySelector('thead tr');

        // 点击表头行整条激活全选
        if (theadRow && selectAllInGroup) {
            theadRow.addEventListener('click', (e) => {
                // 如果直接点击的是复选框本身，则无需额外逻辑，由 bindTableSelection 处理
                if (e.target === selectAllInGroup) return;
                
                selectAllInGroup.checked = !selectAllInGroup.checked;
                // 手动触发 change 事件以执行 UIComponents.bindTableSelection 中的逻辑
                selectAllInGroup.dispatchEvent(new Event('change'));
            });
        }
        
        // 使用通用绑定逻辑，并传入全局 CheckState.selectedPaths
        UIComponents.bindTableSelection({
            tableBody: tbody,
            selectAllCheckbox: selectAllInGroup,
            selectedSet: CheckState.selectedPaths,
            onSelectionChange: () => this.updateFloatingBar()
        });

        tbody.querySelectorAll('.clickable-row').forEach(tr => {
            if (CheckState.settings && CheckState.settings.file_repository.quick_view_thumbnail) {
                tr.addEventListener('mouseenter', (e) => UIComponents.showQuickPreview(e, tr.getAttribute('data-thumbnail')));
                tr.addEventListener('mousemove', (e) => UIComponents.moveQuickPreview(e));
                tr.addEventListener('mouseleave', () => UIComponents.hideQuickPreview());
            }
        });

        return groupEl;
    },

    /**
     * 用途说明：更新底部操作按钮的显示状态及选中计数
     * 入参说明：无
     * 返回值说明：无
     */
    updateFloatingBar() {
        const checkedCount = CheckState.selectedPaths.size;
        const { globalDeleteBtn } = this.elements;
        if (checkedCount > 0) {
            globalDeleteBtn.classList.remove('hidden');
            globalDeleteBtn.textContent = `移入回收站 (${checkedCount})`;
        } else {
            globalDeleteBtn.classList.add('hidden');
        }
    }
};

// --- API 交互模块 ---
const DuplicateCheckAPI = {
    /**
     * 用途说明：向后端发送请求开始查重任务
     * 入参说明：无
     * 返回值说明：无
     */
    async start() {
        try {
            const response = await Request.post('/api/file_repository/duplicate/check', {}, {}, true);
            if (response.status === 'success') {
                Toast.show('查重任务已启动');
                CheckState.results = [];
                CheckState.selectedPaths.clear();
                UIController.toggleView(ProgressStatus.PROCESSING);
                App.startPolling();
            } else {
                Toast.show(response.message);
            }
        } catch (error) {
            Toast.show('启动失败');
        }
    },

    /**
     * 用途说明：向后端发送请求停止查重任务
     * 入参说明：无
     * 返回值说明：无
     */
    async stop() {
        if (!confirm('确定要终止当前的查重任务吗？')) return;
        try {
            const response = await Request.post('/api/file_repository/duplicate/stop', {}, {}, true);
            if (response.status === 'success') Toast.show('正在停止任务...');
        } catch (error) {
            Toast.show('请求停止失败');
        }
    },

    /**
     * 用途说明：向后端轮询查重任务的最新进度
     * 入参说明：无
     * 返回值说明：Object - 包含 status 和 progress
     */
    async fetchProgress() {
        try {
            const response = await Request.get('/api/file_repository/duplicate/progress', {}, false);
            if (response.status === 'success') return response.data;
        } catch (error) {
            console.error('获取查重进度失败:', error);
        }
        return null;
    },

    /**
     * 用途说明：分页获取查重结果数据
     * 入参说明：page (int), limit (int), similarityType (string)
     * 返回值说明：Object - PaginationResult
     */
    async fetchList(page, limit, similarityType = '') {
        try {
            const queryParams = { page: page, limit: limit };
            if (similarityType) queryParams.similarity_type = similarityType;

            const query = new URLSearchParams(queryParams).toString();
            const response = await Request.get('/api/file_repository/duplicate/list?' + query, {}, true);
            if (response.status === 'success') return response.data;
        } catch (error) {
            console.error('获取结果列表失败:', error);
        }
        return null;
    },

    /**
     * 用途说明：调用通用移入回收站 API 批量文件
     * 入参说明：paths (Array) - 文件路径列表
     * 返回值说明：Object - 后端响应结果
     */
    async moveToRecycleBin(paths) {
        try {
            return await Request.post('/api/file_repository/move_to_recycle_bin', { file_paths: paths }, {}, true);
        } catch (error) {
            console.error('移入回收站文件请求失败:', error);
            return { status: 'error', message: '请求失败' };
        }
    }
};

// --- 应用入口 ---
const App = {
    /**
     * 用途说明：应用启动入口
     * 入参说明：无
     * 返回值说明：无
     */
    async init() {
        UIController.init();
        await this.loadSettings();

        // 初始化时检查一次进度
        const data = await DuplicateCheckAPI.fetchProgress();
        if (data) {
            if (data.status === ProgressStatus.PROCESSING) {
                UIController.toggleView(ProgressStatus.PROCESSING);
                this.startPolling();
            } else if (data.status === ProgressStatus.COMPLETED) {
                this.loadResults(1);
            } else {
                UIController.toggleView(ProgressStatus.IDLE);
            }
        }
    },

    async loadSettings() {
        try {
            const response = await Request.get('/api/setting/get');
            if (response.status === 'success') {
                CheckState.settings = response.data;
            }
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    },

    /**
     * 用途说明：加载指定页码的结果数据
     * 入参说明：page (int) - 目标页码
     * 返回值说明：无
     */
    async loadResults(page) {
        const data = await DuplicateCheckAPI.fetchList(page, CheckState.limit, CheckState.similarityType);
        if (data) {
            CheckState.setPaginationData(data, CheckState.previousExpandedStates);
            CheckState.previousExpandedStates = null; 
            UIController.toggleView(ProgressStatus.COMPLETED);
            UIController.renderResults();
        }
    },

    /**
     * 用途说明：切换页码逻辑
     * 入参说明：page (int)
     * 返回值说明：无
     */
    async changePage(page) {
        if (page < 1) return;
        const expandedStatesMap = {};
        CheckState.results.forEach(group => {
            expandedStatesMap[group.id] = group.isExpanded;
        });
        CheckState.previousExpandedStates = expandedStatesMap; 
        await this.loadResults(page);
        window.scrollTo(0, 0);
    },

    /**
     * 用途说明：批量移入回收站并刷新列表
     * 入参说明：paths (Array) - 路径列表, confirmMsg (String) - 确认提示词
     * 返回值说明：无
     */
    async moveToRecycleBin(paths, confirmMsg) {
        if (!paths || paths.length === 0) return;

        UIComponents.showConfirmModal({
            message: confirmMsg,
            confirmText: '确定移动',
            onConfirm: async () => {
                const response = await DuplicateCheckAPI.moveToRecycleBin(paths);
                if (response.status === 'success') {
                    Toast.show(response.message || '已移入回收站');
                    CheckState.selectedPaths.clear(); // 成功后清除选中
                    const expandedStatesMap = {};
                    CheckState.results.forEach(group => {
                        expandedStatesMap[group.id] = group.isExpanded;
                    });
                    CheckState.previousExpandedStates = expandedStatesMap; 
                    this.loadResults(CheckState.page);
                } else {
                    Toast.show(response.message || '移入回收站失败');
                }
            }
        });
    },

    /**
     * 用途说明：开启定时轮询任务状态
     * 入参说明：无
     * 返回值说明：无
     */
    startPolling() {
        if (CheckState.pollingInterval) return;
        CheckState.pollingInterval = setInterval(async () => {
            const data = await DuplicateCheckAPI.fetchProgress();
            if (!data) return;

            if (data.status === ProgressStatus.PROCESSING) {
                UIController.updateProgress(data.progress);
            } else {
                this.stopPolling();
                if (data.status === ProgressStatus.COMPLETED) {
                    Toast.show('查重已完成');
                    this.loadResults(1);
                } else {
                    UIController.toggleView(data.status);
                }
            }
        }, 1500);
    },

    /**
     * 用途说明：停止轮询
     * 入参说明：无
     * 返回值说明：无
     */
    stopPolling() {
        if (CheckState.pollingInterval) {
            clearInterval(CheckState.pollingInterval);
            CheckState.pollingInterval = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
