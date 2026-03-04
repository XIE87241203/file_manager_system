/**
 * 用途说明：查重页面 logic 处理，负责触发查重任务、进度监控以及查重结果的分页展示与交互。
 */

// --- 状态管理 ---
const State = {
    results: [],
    page: 1,
    limit: 20,
    total: 0,
    similarityType: '', // 存储当前的筛选类型
    lastCheckTime: '--',
    pollingInterval: null,
    settings: null, // 存储系统设置
    previousExpandedStates: null, // 用途说明：存储上一页结果的展开/收起状态，用于刷新后保留状态
    selectedPaths: new Set(), // 存储选中的文件路径，以保持跨页选中状态

    /**
     * 用途说明：更新结果列表及分页信息
     * 入参说明：
     *   data (Object): 后端返回的 PaginationResult 结构
     *   expandedStatesMap (Object|null): 存储分组ID到isExpanded状态的映射，用于恢复分组的展开状态
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
            summaryTime: document.getElementById('summary-time'),
            globalDeleteBtn: document.getElementById('btn-delete-selected-global'),
            filterSimilarityType: document.getElementById('filter-similarity-type')
        };

        this.renderHeader(ProgressStatus.IDLE);
    },

    /**
     * 用途说明：渲染顶部导航栏，根据任务状态切换“开始”与“停止”按钮
     * 入参说明：status (String) - ProgressStatus 枚举值
     * 返回值说明：无
     */
    renderHeader(status) {
        if (typeof HeaderToolbar === 'undefined') return;
        const isProcessing = status === ProgressStatus.PROCESSING;
        const menuIcon = '../../common/header_toolbar/icon/search_icon.svg';
        HeaderToolbar.init({
            title: I18nManager.t('duplicate_check.title'),
            showBack: true,
            menuIcon: menuIcon,
            menuCallback: () => {
                if (isProcessing) {
                    App.handleStop();
                } else {
                    App.handleStart();
                }
            }
        });
        const menuBtn = document.getElementById('btn-menu');
        if (menuBtn) {
            menuBtn.title = isProcessing ? I18nManager.t('duplicate_check.stop_check') : I18nManager.t('duplicate_check.start_check');
            const menuImg = menuBtn.querySelector('img');
            if (menuImg) menuImg.alt = menuBtn.title;
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
            UIComponents.showProgressBar('#scanning-container', I18nManager.t('duplicate_check.preparing'));
        } else {
            this.renderHeader(ProgressStatus.IDLE);
            scanningContainer.classList.add('hidden');
            UIComponents.hideProgressBar('#scanning-container');

            if (status === ProgressStatus.COMPLETED || (State.results && State.results.length > 0) || State.similarityType !== '') {
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
        const { wrapper, summaryBar, summaryGroups, summaryTime } = this.elements;
        wrapper.innerHTML = '';

        const results = State.results;
        if (!results || results.length === 0) {
            summaryBar.classList.remove('hidden');
            wrapper.innerHTML = `<div style="text-align: center; color: #9aa0a6; padding-top: 100px;">${I18nManager.t('duplicate_check.empty_results')}</div>`;
            PageBar.init({
                containerId: 'pagination-container',
                totalItems: 0,
                pageSize: State.limit,
                currentPage: 1,
                onPageChange: (newPage) => App.changePage(newPage)
            });
            this.updateFloatingBar();
            return;
        }

        summaryBar.classList.remove('hidden');
        summaryGroups.textContent = I18nManager.t('duplicate_check.summary_groups', { total: State.total });
        summaryTime.textContent = I18nManager.t('duplicate_check.summary_time', { time: State.lastCheckTime || '--' });

        results.forEach(group => {
            const groupEl = this.createGroupElement(group);
            wrapper.appendChild(groupEl);
        });

        // 更新公用分页组件
        PageBar.init({
            containerId: 'pagination-container',
            totalItems: State.total,
            pageSize: State.limit,
            currentPage: State.page,
            onPageChange: (newPage) => App.changePage(newPage)
        });

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
        const groupType = group.group_name || I18nManager.t('duplicate_check.group_default_name');

        groupEl.innerHTML = `
            <div class="group-header">
                <div class="group-info">
                    <span class="group-title" title="${groupType}">${groupType}</span>
                    <span class="group-count">${I18nManager.t('duplicate_check.file_count', { count: fileCount })}</span>
                    <span class="group-md5">ID: ${group.id}</span>
                    <span class="expand-icon">▶</span>
                </div>
            </div>
            <div class="group-content">
                <table class="file-item-table">
                    <thead>
                        <tr class="header-row-clickable">
                            <th class="col-dup-name" data-i18n="duplicate_check.col_name"></th>
                            <th class="col-dup-duration" data-i18n="duplicate_check.col_duration"></th>
                            <th class="col-dup-codec" data-i18n="duplicate_check.col_codec"></th>
                            <th class="col-dup-similarity" data-i18n="duplicate_check.col_similarity"></th>
                            <th class="col-dup-size" data-i18n="duplicate_check.col_size"></th>
                            <th class="col-dup-path" data-i18n="duplicate_check.col_path"></th>
                            <th class="col-dup-check">
                                <input type="checkbox" class="file-checkbox select-all-in-group">
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        ${files.map(f => {
                            const info = f.file_info;
                            const isChecked = State.selectedPaths.has(info.file_path);
                            const fileName = info.file_name || I18nManager.t('duplicate_check.unknown_file');
                            const fileSizeStr = CommonUtils.formatFileSize(info.file_size);
                            const durationStr = info.file_type === 'video' ? CommonUtils.formatDuration(info.video_duration) : '-';
                            const codecStr = (info.file_type === 'video' && info.video_codec) ? info.video_codec : '-';

                            const typeMap = {
                                'md5': I18nManager.t('duplicate_check.type_md5'),
                                'hash': I18nManager.t('duplicate_check.type_image'),
                                'video_feature': I18nManager.t('duplicate_check.type_video')
                            };
                            const typeStr = typeMap[f.similarity_type] || f.similarity_type;
                            const rateStr = (f.similarity_rate * 100).toFixed(1) + '%';
                            const similarityDisplay = `${typeStr}(${rateStr})`;

                            return `
                                <tr class="clickable-row ${isChecked ? 'selected-row' : ''}" data-path="${info.file_path}" data-thumbnail="${info.thumbnail_path || ''}">
                                    <td class="col-dup-name" title="${fileName}">${fileName}</td>
                                    <td class="col-dup-duration">${durationStr}</td>
                                    <td class="col-dup-codec">${codecStr}</td>
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

        I18nManager.render(groupEl);

        const header = groupEl.querySelector('.group-header');
        header.addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            groupEl.classList.toggle('expanded');
            const groupId = groupEl.getAttribute('data-group-id');
            const targetGroup = State.results.find(g => String(g.id) === groupId);
            if (targetGroup) {
                targetGroup.isExpanded = groupEl.classList.contains('expanded');
            }
        });

        const tbody = groupEl.querySelector('tbody');
        const selectAllInGroup = groupEl.querySelector('.select-all-in-group');
        const theadRow = groupEl.querySelector('thead tr');

        if (theadRow && selectAllInGroup) {
            theadRow.addEventListener('click', (e) => {
                if (e.target === selectAllInGroup) return;
                selectAllInGroup.checked = !selectAllInGroup.checked;
                selectAllInGroup.dispatchEvent(new Event('change'));
            });
        }
        
        UIComponents.bindTableSelection({
            tableBody: tbody,
            selectAllCheckbox: selectAllInGroup,
            selectedSet: State.selectedPaths,
            onSelectionChange: () => this.updateFloatingBar()
        });

        tbody.querySelectorAll('.clickable-row').forEach(tr => {
            if (State.settings && State.settings.file_repository.quick_view_thumbnail) {
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
        const checkedCount = State.selectedPaths.size;
        const { globalDeleteBtn } = this.elements;
        if (!globalDeleteBtn) return;

        if (checkedCount > 0) {
            globalDeleteBtn.classList.remove('hidden');
            globalDeleteBtn.setAttribute('title', I18nManager.t('duplicate_check.move_to_recycle_count', { count: checkedCount }));
        } else {
            globalDeleteBtn.classList.add('hidden');
        }
    }
};

// --- 应用逻辑主入口 ---
const App = {
    /**
     * 用途说明：应用启动入口
     * 入参说明：无
     * 返回值说明：无
     */
    init() {
        // 初始化多语言
        I18nManager.init();
        I18nManager.render();

        UIController.init();
        this.bindEvents();
        this.loadSettings();

        // 初始化时检查一次进度
        DuplicateCheckAPI.getProgress(
            (data) => {
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
            (err) => console.error(err)
        );
    },

    /**
     * 用途说明：加载系统设置
     * 入参说明：无
     * 返回值说明：无
     */
    loadSettings() {
        DuplicateCheckAPI.getSettings(
            (data) => { State.settings = data; },
            (err) => console.error(I18nManager.t('common.error'), err)
        );
    },

    /**
     * 用途说明：绑定页面交互事件
     * 入参说明：无
     * 返回值说明：无
     */
    bindEvents() {
        const { globalDeleteBtn, filterSimilarityType } = UIController.elements;

        // 绑定全局删除按钮
        if (globalDeleteBtn) {
            globalDeleteBtn.onclick = () => {
                const paths = Array.from(State.selectedPaths);
                if (paths.length > 0) {
                    this.handleMoveToRecycleBin(paths);
                }
            };
        }

        // 绑定筛选事件
        if (filterSimilarityType) {
            filterSimilarityType.onchange = () => {
                State.similarityType = filterSimilarityType.value;
                this.loadResults(1);
            };
        }
    },

    /**
     * 用途说明：处理开始查重逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleStart() {
        DuplicateCheckAPI.startCheck(
            () => {
                Toast.show(I18nManager.t('duplicate_check.check_started'));
                State.results = [];
                State.selectedPaths.clear();
                UIController.toggleView(ProgressStatus.PROCESSING);
                this.startPolling();
            },
            (err) => Toast.show(err || I18nManager.t('duplicate_check.start_failed'))
        );
    },

    /**
     * 用途说明：处理停止查重逻辑
     * 入参说明：无
     * 返回值说明：无
     */
    handleStop() {
        UIComponents.showConfirmModal({
            title: I18nManager.t('common.hint'),
            message: I18nManager.t('duplicate_check.stop_confirm'),
            onConfirm: () => {
                DuplicateCheckAPI.stopCheck(
                    () => Toast.show(I18nManager.t('duplicate_check.stopping')),
                    (err) => Toast.show(err || I18nManager.t('duplicate_check.stop_failed'))
                );
            }
        });
    },

    /**
     * 用途说明：加载指定页码的结果数据
     * @param {number} page - 入参说明：目标页码
     * @returns {void} - 返回值说明：无
     */
    loadResults(page) {
        const params = {
            page: page,
            limit: State.limit,
            similarity_type: State.similarityType
        };
        DuplicateCheckAPI.getDuplicateList(
            params,
            (data) => {
                State.setPaginationData(data, State.previousExpandedStates);
                State.previousExpandedStates = null;

                // 结果加载成功后，获取最新的查重时间
                DuplicateCheckAPI.getLatestCheckTime(
                    (timeData) => {
                        State.lastCheckTime = timeData;
                        UIController.toggleView(ProgressStatus.COMPLETED);
                        UIController.renderResults();
                    },
                    () => {
                        UIController.toggleView(ProgressStatus.COMPLETED);
                        UIController.renderResults();
                    }
                );
            },
            (err) => Toast.show(err)
        );
    },

    /**
     * 用途说明：切换页码逻辑
     * @param {number} page - 入参说明：目标页码
     * @returns {void} - 返回值说明：无
     */
    changePage(page) {
        if (page < 1) return;
        const expandedStatesMap = {};
        State.results.forEach(group => {
            expandedStatesMap[group.id] = group.isExpanded;
        });
        State.previousExpandedStates = expandedStatesMap;
        this.loadResults(page);
        window.scrollTo(0, 0);
    },

    /**
     * 用途说明：批量移入回收站并刷新列表
     * @param {Array} paths - 入参说明：路径列表
     * @returns {void} - 返回值说明：无
     */
    handleMoveToRecycleBin(paths) {
        if (!paths || paths.length === 0) return;

        UIComponents.showConfirmModal({
            title: I18nManager.t('duplicate_check.delete_confirm_title'),
            message: I18nManager.t('duplicate_check.delete_confirm_msg', { count: paths.length }),
            onConfirm: () => {
                DuplicateCheckAPI.moveToRecycleBin(
                    paths,
                    (res) => {
                        Toast.show(res.message || I18nManager.t('common.success'));
                        State.selectedPaths.clear();
                        const expandedStatesMap = {};
                        State.results.forEach(group => {
                            expandedStatesMap[group.id] = group.isExpanded;
                        });
                        State.previousExpandedStates = expandedStatesMap;
                        this.loadResults(State.page);
                    },
                    (err) => Toast.show(err)
                );
            }
        });
    },

    /**
     * 用途说明：开启定时轮询任务状态
     * 入参说明：无
     * 返回值说明：无
     */
    startPolling() {
        if (State.pollingInterval) return;
        State.pollingInterval = setInterval(() => {
            DuplicateCheckAPI.getProgress(
                (data) => {
                    if (!data) return;
                    if (data.status === ProgressStatus.PROCESSING) {
                        UIController.updateProgress(data.progress);
                    } else {
                        this.stopPolling();
                        if (data.status === ProgressStatus.COMPLETED) {
                            Toast.show(I18nManager.t('common.success'));
                            this.loadResults(1);
                        } else {
                            UIController.toggleView(data.status);
                        }
                    }
                },
                (err) => {
                    console.error(err);
                    this.stopPolling();
                }
            );
        }, 1500);
    },

    /**
     * 用途说明：停止轮询
     * 入参说明：无
     * 返回值说明：无
     */
    stopPolling() {
        if (State.pollingInterval) {
            clearInterval(State.pollingInterval);
            State.pollingInterval = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
