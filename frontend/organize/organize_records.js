/**
 * @description 整理记录页面逻辑处理，负责记录列表分页展示（时间倒序）、文件名悬停显示路径与右上角 CSV 导出。
 */

// --- 状态管理 ---
const State = {
    page: 1, // 当前页码（从 1 开始）
    pageSize: 20, // 每页条数
    total: 0, // 整理记录总条数
    items: [], // 当前页记录列表
    exporting: false // 是否正在导出（防止重复触发）
};

// --- UI 控制模块 ---
const UIController = {
    elements: {},

    /**
     * @description 用途说明：初始化页面 UI，渲染多语言并初始化顶部栏（右上角为导出按钮）。
     * @returns {void} - 返回值说明：无
     */
    init() {
        I18nManager.init();
        I18nManager.render();

        HeaderToolbar.init({
            title: I18nManager.t('organize.records.title'),
            showBack: true,
            backCallback: () => { window.location.href = '../home/home.html'; },
            menuIcon: '../common/header_toolbar/icon/export_icon.svg',
            menuCallback: () => App.handleExport()
        });
        // 工具栏组件默认标题为“菜单”，此处按导出语义覆盖提示文案
        const menuBtn = document.getElementById('btn-menu');
        if (menuBtn) {
            menuBtn.title = I18nManager.t('organize.records.export_title');
            menuBtn.setAttribute('aria-label', I18nManager.t('organize.records.export_title'));
        }

        this.elements = {
            summaryText: document.getElementById('records-summary-text'),
            table: document.getElementById('records-table'),
            tableBody: document.getElementById('records-table-body'),
            empty: document.getElementById('records-empty'),
            pageBar: document.getElementById('records-page-bar'),
            menuBtn: menuBtn
        };

        // 空状态引导按钮：前往文件整理页
        const goBtn = document.getElementById('empty-go-btn');
        if (goBtn) {
            goBtn.onclick = () => { window.location.href = 'organize_task.html'; };
        }
    },

    /**
     * @description 用途说明：渲染记录总数摘要条。
     * @returns {void} - 返回值说明：无
     */
    renderSummary() {
        this.elements.summaryText.textContent = I18nManager.t('organize.records.summary', { count: State.total });
    },

    /**
     * @description 用途说明：渲染当前页记录表格。序号按全局倒序连续编号；
     *   整理后/整理前文件名单元格通过 title 属性悬停展示对应完整路径。
     * @returns {void} - 返回值说明：无
     */
    renderTable() {
        const hasItems = State.items.length > 0;
        this.elements.table.classList.toggle('hidden', !hasItems);
        this.elements.empty.classList.toggle('hidden', hasItems);
        this.elements.pageBar.classList.toggle('hidden', State.total === 0);

        const rows = State.items.map((item, index) => {
            const seq = (State.page - 1) * State.pageSize + index + 1;
            const organizedPath = this.escapeHtml(item.organized_path || '');
            const originalPath = this.escapeHtml(item.original_path || '');
            return `
                <tr>
                    <td class="seq-cell">${seq}</td>
                    <td class="name-cell organized-name" title="${organizedPath}">${this.escapeHtml(item.organized_name || '')}</td>
                    <td class="name-cell original-name" title="${originalPath}">${this.escapeHtml(item.original_name || '')}</td>
                    <td class="time-cell">${this.escapeHtml(item.organize_time || '')}</td>
                </tr>
            `;
        });
        this.elements.tableBody.innerHTML = rows.join('');
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
     * @description 用途说明：加载指定页的整理记录（后端按整理时间倒序返回）。
     * @param {number} page - 入参说明：目标页码（从 1 开始）。
     * @returns {void} - 返回值说明：无
     */
    loadPage(page) {
        OrganizeRecordsRequest.getRecords(
            page,
            State.pageSize,
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
     * @description 用途说明：处理右上角导出按钮点击：导出全部整理记录为 CSV 并触发下载。
     *   无记录时给出提示；导出进行中禁用按钮防止重复触发。
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