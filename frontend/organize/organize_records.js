/**
 * @description 整理记录页面逻辑处理，负责记录列表分页展示（时间倒序）、文件名关键词搜索（同时匹配整理前/整理后文件名）、
 *   命中文本高亮、文件名悬停显示路径与右上角 CSV 导出（导出跟随当前搜索条件）。
 */

// --- 状态管理 ---
const State = {
    page: 1, // 当前页码（从 1 开始）
    pageSize: 20, // 每页条数
    total: 0, // 符合当前搜索条件的记录总条数
    items: [], // 当前页记录列表
    keyword: '', // 搜索关键词（空串表示不筛选，同时匹配整理前/整理后文件名）
    exporting: false // 是否正在导出（防止重复触发）
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化页面 UI，渲染多语言并初始化搜索顶部栏（中部搜索框，右上角为导出按钮），
     *   并在搜索框内追加清除按钮（有关键词时显示）。
     * @returns {void} - 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        SearchHeaderToolbar.init({
            searchHint: I18nManager.t('organize.records.search_placeholder'),
            showBack: true,
            backCallback: () => { window.location.href = '../home/home.html'; },
            menuIcon: '/common/themes/light/icons/export_icon.svg',
            menuCallback: () => App.handleExport(),
            searchCallback: (content) => App.handleSearch(content)
        });
        // 工具栏组件默认标题为“菜单”，此处按导出语义覆盖提示文案
        const menuBtn = document.getElementById('btn-menu');
        if (menuBtn) {
            menuBtn.title = I18nManager.t('organize.records.export_title');
            menuBtn.setAttribute('aria-label', I18nManager.t('organize.records.export_title'));
        }

        const searchInput = document.getElementById('search-input');
        // 搜索框内清除按钮：组件未提供，页面级追加（样式见 organize_records.css）
        const clearBtn = document.createElement('div');
        clearBtn.id = 'btn-search-clear';
        clearBtn.className = 'search-clear-btn hidden';
        clearBtn.title = I18nManager.t('organize.records.search_clear_title');
        clearBtn.setAttribute('aria-label', I18nManager.t('organize.records.search_clear_title'));
        clearBtn.innerHTML = '<span class="theme-icon icon-close" aria-hidden="true"></span>';
        const searchContainer = document.querySelector('.search-input-container');
        if (searchContainer) {
            searchContainer.insertBefore(clearBtn, document.getElementById('btn-search-trigger'));
        }
        clearBtn.onclick = () => App.clearSearch();
        if (searchInput) {
            // 输入内容变化时同步清除按钮可见性（搜索仍由回车/搜索按钮触发，与其他页面一致）
            searchInput.addEventListener('input', () => {
                clearBtn.classList.toggle('hidden', !searchInput.value);
            });
        }

        this.elements = {
            summaryText: document.getElementById('records-summary-text'),
            table: document.getElementById('records-table'),
            tableBody: document.getElementById('records-table-body'),
            empty: document.getElementById('records-empty'),
            emptyTitle: document.getElementById('records-empty-title'),
            emptyHint: document.getElementById('records-empty-hint'),
            pageBar: document.getElementById('records-page-bar'),
            menuBtn: menuBtn,
            searchInput: searchInput,
            searchClearBtn: clearBtn
        };

        // 空状态引导按钮：前往文件整理页 / 清除搜索
        const goBtn = document.getElementById('empty-go-btn');
        if (goBtn) {
            goBtn.onclick = () => { window.location.href = 'organize_task.html'; };
        }
        const emptyClearBtn = document.getElementById('empty-clear-btn');
        if (emptyClearBtn) {
            emptyClearBtn.onclick = () => App.clearSearch();
        }
    },

    /**
     * @description 用途说明：渲染记录总数摘要条（搜索中展示关键词与匹配数）。
     * @returns {void} - 返回值说明：无
     */
    renderSummary() {
        this.elements.summaryText.textContent = State.keyword
            ? I18nManager.t('organize.records.summary_filtered', { count: State.total, keyword: State.keyword })
            : I18nManager.t('organize.records.summary', { count: State.total });
    },

    /**
     * @description 用途说明：渲染当前页记录表格。序号按全局倒序连续编号；
     *   整理后/整理前文件名单元格通过 title 属性悬停展示对应完整路径；搜索命中的文本片段高亮。
     * @returns {void} - 返回值说明：无
     */
    renderTable() {
        const hasItems = State.items.length > 0;
        this.elements.table.classList.toggle('hidden', !hasItems);
        this.elements.empty.classList.toggle('hidden', hasItems);
        this.elements.pageBar.classList.toggle('hidden', State.total === 0);
        if (!hasItems) {
            this.renderEmptyVariant();
        }

        const rows = State.items.map((item, index) => {
            const seq = (State.page - 1) * State.pageSize + index + 1;
            const organizedPath = this.escapeHtml(item.organized_path || '');
            const originalPath = this.escapeHtml(item.original_path || '');
            return `
                <tr>
                    <td class="seq-cell">${seq}</td>
                    <td class="name-cell organized-name" title="${organizedPath}">${this.highlightHtml(item.organized_name || '', State.keyword)}</td>
                    <td class="name-cell original-name" title="${originalPath}">${this.highlightHtml(item.original_name || '', State.keyword)}</td>
                    <td class="time-cell">${this.escapeHtml(item.organize_time || '')}</td>
                </tr>
            `;
        });
        this.elements.tableBody.innerHTML = rows.join('');
    },

    /**
     * @description 用途说明：渲染空状态文案变体：搜索无结果时展示“没有找到匹配的记录”与清除搜索按钮，
     *   否则展示默认空状态与前往整理按钮（同步更新 data-i18n 以便语言切换重渲染时保持一致）。
     * @returns {void} - 返回值说明：无
     */
    renderEmptyVariant() {
        const noResult = Boolean(State.keyword);
        const titleKey = noResult ? 'organize.records.no_result' : 'organize.records.empty';
        const hintKey = noResult ? 'organize.records.no_result_hint' : 'organize.records.empty_hint';
        this.elements.emptyTitle.setAttribute('data-i18n', titleKey);
        this.elements.emptyHint.setAttribute('data-i18n', hintKey);
        this.elements.emptyTitle.textContent = I18nManager.t(titleKey);
        this.elements.emptyHint.textContent = I18nManager.t(hintKey);
        document.getElementById('empty-go-btn').classList.toggle('hidden', noResult);
        document.getElementById('empty-clear-btn').classList.toggle('hidden', !noResult);
    },

    /**
     * @description 用途说明：渲染分页栏（总数为 0 时隐藏）。
     * @returns {void} - 返回值说明：无
     */
    renderPageBar() {
        if (State.total === 0) return;
        PageBar.init({
            containerId: 'records-page-bar',
            totalItems: State.total,
            pageSize: State.pageSize,
            currentPage: State.page,
            onPageChange: (page) => App.loadPage(page)
        });
    },

    /**
     * @description 用途说明：切换导出按钮的进行中禁用态。
     * @param {boolean} exporting - 入参说明：true 表示导出进行中（禁用按钮），false 恢复可用。
     * @returns {void} - 返回值说明：无
     */
    setExporting(exporting) {
        State.exporting = exporting;
        if (this.elements.menuBtn) {
            this.elements.menuBtn.classList.toggle('export-disabled', exporting);
            // 导出进行中同步切换按钮提示文案，给出可感知的状态反馈
            this.elements.menuBtn.title = I18nManager.t(exporting ? 'organize.records.exporting' : 'organize.records.export_title');
        }
    },

    /**
     * @description 用途说明：HTML 转义，防止文件名/路径中的特殊字符破坏页面结构。
     * @param {string} text - 入参说明：待转义的原始文本。
     * @returns {string} - 返回值说明：转义后的安全文本。
     */
    escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    /**
     * @description 用途说明：生成带搜索命中高亮的 HTML：先按关键词（不区分大小写）切分原文，
     *   各片段分别转义后再用 mark 标签包裹命中部分，保证转义与高亮互不干扰。
     * @param {string} text - 入参说明：原始文件名文本。
     * @param {string} keyword - 入参说明：搜索关键词，空串时仅做转义。
     * @returns {string} - 返回值说明：可安全插入 innerHTML 的高亮文本。
     */
    highlightHtml(text, keyword) {
        const raw = String(text || '');
        if (!keyword) return this.escapeHtml(raw);
        const lower = raw.toLowerCase();
        const kw = keyword.toLowerCase();
        let html = '';
        let cursor = 0;
        while (cursor <= raw.length) {
            const idx = lower.indexOf(kw, cursor);
            if (idx === -1) {
                html += this.escapeHtml(raw.slice(cursor));
                break;
            }
            html += this.escapeHtml(raw.slice(cursor, idx))
                + '<mark class="search-hit">' + this.escapeHtml(raw.slice(idx, idx + kw.length)) + '</mark>';
            cursor = idx + kw.length;
        }
        return html;
    }
};

// --- 应用入口模块 ---
const App = {
    /**
     * @description 用途说明：页面入口，初始化 UI 并加载第一页整理记录。
     * @returns {void} - 返回值说明：无
     */
    init() {
        UIController.init();
        this.loadPage(1);
    },

    /**
     * @description 用途说明：处理搜索触发（回车或搜索按钮）：记录关键词并回到第一页刷新列表。
     * @param {string} content - 入参说明：搜索框内容（组件已去除首尾空白）。
     * @returns {void} - 返回值说明：无
     */
    handleSearch(content) {
        State.keyword = content || '';
        if (UIController.elements.searchClearBtn) {
            UIController.elements.searchClearBtn.classList.toggle('hidden', !State.keyword);
        }
        this.loadPage(1);
    },

    /**
     * @description 用途说明：清除搜索：清空输入框与关键词，回到第一页展示全部记录。
     * @returns {void} - 返回值说明：无
     */
    clearSearch() {
        State.keyword = '';
        if (UIController.elements.searchInput) {
            UIController.elements.searchInput.value = '';
        }
        if (UIController.elements.searchClearBtn) {
            UIController.elements.searchClearBtn.classList.add('hidden');
        }
        this.loadPage(1);
    },

    /**
     * @description 用途说明：加载指定页的整理记录（后端按整理时间倒序返回，携带当前搜索关键词）。
     * @param {number} page - 入参说明：目标页码（从 1 开始）。
     * @returns {void} - 返回值说明：无
     */
    loadPage(page) {
        OrganizeRecordsRequest.getRecords(
            page,
            State.pageSize,
            State.keyword,
            (data) => {
                State.total = (data && data.total) || 0;
                State.page = (data && data.page) || page;
                State.items = (data && data.items) || [];
                UIController.renderSummary();
                UIController.renderTable();
                UIController.renderPageBar();
            },
            (message) => {
                Toast.show(message || I18nManager.t('organize.records.load_failed'));
            }
        );
    },

    /**
     * @description 用途说明：处理右上角导出按钮点击：按当前搜索条件导出整理记录为 CSV 并触发下载。
     *   无匹配记录时给出提示；导出进行中禁用按钮防止重复触发。
     * @returns {void} - 返回值说明：无
     */
    handleExport() {
        if (State.exporting) return;
        if (State.total === 0) {
            Toast.show(I18nManager.t('organize.records.export_empty'));
            return;
        }
        UIController.setExporting(true);
        OrganizeRecordsRequest.exportRecords(
            State.keyword,
            () => {
                UIController.setExporting(false);
                Toast.show(I18nManager.t('organize.records.export_success'));
            },
            (message) => {
                UIController.setExporting(false);
                Toast.show(message || I18nManager.t('organize.records.export_failed'));
            }
        );
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());