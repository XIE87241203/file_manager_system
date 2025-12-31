/**
 * 用途说明：文件仓库页面逻辑处理，负责文件列表展示、分页、排序、搜索以及异步扫描任务的生命周期管理。
 */

let currentPage = 1;
const pageSize = 15;
let scanInterval = null;

// 排序状态变量
let currentSortBy = 'scan_time';
let currentOrder = 'DESC';
// 搜索状态变量
let currentSearch = '';
let currentSearchHistory = false;

/**
 * 用途说明：页面加载初始化。
 * 入参说明：无。
 * 返回值说明：无。
 */
document.addEventListener('DOMContentLoaded', () => {
    // 1. 绑定返回按钮逻辑
    const backBtn = document.getElementById('nav-back-btn');
    if (backBtn) {
        backBtn.onclick = () => {
            window.history.back();
        };
    }

    // 2. 绑定搜索功能
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const historyCheckbox = document.getElementById('search-history-checkbox');

    const handleSearch = () => {
        currentSearch = searchInput.value.trim();
        currentSearchHistory = historyCheckbox ? historyCheckbox.checked : false;
        currentPage = 1;
        loadFileList(currentPage);
    };

    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    }
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
    }
    if (historyCheckbox) {
        historyCheckbox.addEventListener('change', handleSearch);
    }

    // 3. 加载文件列表
    loadFileList(currentPage);

    // 4. 绑定建立索引按钮事件
    const scanBtn = document.getElementById('btn-scan');
    if (scanBtn) {
        scanBtn.addEventListener('click', startScanTask);
    }

    // 5. 绑定停止扫描按钮事件
    const stopBtn = document.getElementById('btn-stop');
    if (stopBtn) {
        stopBtn.addEventListener('click', stopScanTask);
    }

    // 6. 绑定分页按钮
    document.getElementById('btn-prev-page').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadFileList(currentPage);
        }
    });

    document.getElementById('btn-next-page').addEventListener('click', () => {
        currentPage++;
        loadFileList(currentPage);
    });

    // 7. 绑定表头排序事件
    initTableHeaderSort();

    // 8. 页面进入时立即检查一次扫描状态
    checkScanProgress();
});

/**
 * 用途说明：初始化表头排序功能。
 * 入参说明：无。
 * 返回值说明：无。
 */
function initTableHeaderSort() {
    const sortableHeaders = document.querySelectorAll('th.sortable');
    sortableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const field = th.getAttribute('data-field');
            
            // 如果点击的是当前排序字段，则切换顺序
            if (currentSortBy === field) {
                currentOrder = currentOrder === 'ASC' ? 'DESC' : 'ASC';
            } else {
                // 如果是新字段，默认降序
                currentSortBy = field;
                currentOrder = 'DESC';
            }
            
            // 更新 UI 样式
            updateHeaderSortUI(field, currentOrder);
            
            // 重新从第一页加载数据
            currentPage = 1;
            loadFileList(currentPage);
        });
    });
}

/**
 * 用途说明：更新表头排序图标和样式。
 * 入参说明：field (str) - 当前排序字段, order (str) - 排序顺序。
 * 返回值说明：无。
 */
function updateHeaderSortUI(field, order) {
    const sortableHeaders = document.querySelectorAll('th.sortable');
    sortableHeaders.forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.getAttribute('data-field') === field) {
            th.classList.add(order === 'ASC' ? 'sort-asc' : 'sort-desc');
        }
    });
}

/**
 * 用途说明：从后端获取文件列表并渲染表格。
 * 入参说明：page (int) - 当前页码。
 * 返回值说明：无。
 */
async function loadFileList(page) {
    try {
        let url = `/api/file_repository/list?page=${page}&limit=${pageSize}&sort_by=${currentSortBy}&order=${currentOrder}`;
        if (currentSearch) {
            url += `&search=${encodeURIComponent(currentSearch)}`;
        }
        if (currentSearchHistory) {
            url += `&search_history=true`;
        }
        
        const response = await Request.get(url, {}, true);
        if (response.status === 'success') {
            renderTable(response.data.list);
            updatePaginationUI(response.data.total, page);
            updateHeaderSortUI(currentSortBy, currentOrder);
        }
    } catch (error) {
        console.error('加载文件列表出错:', error);
    }
}

/**
 * 用途说明：渲染文件表格内容。
 * 入参说明：list (array) - 数据列表。
 * 返回值说明：无。
 */
function renderTable(list) {
    const tbody = document.getElementById('file-list-body');
    tbody.innerHTML = '';

    if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">暂无索引文件</td></tr>';
        return;
    }

    list.forEach(file => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td title="${file.file_name}">${file.file_name}</td>
            <td title="${file.file_path}">${file.file_path}</td>
            <td><code>${file.file_md5}</code></td>
            <td>${file.scan_time}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * 用途说明：更新分页控件显示状态。
 * 入参说明：total (int) - 总数, page (int) - 当前页。
 * 返回值说明：无。
 */
function updatePaginationUI(total, page) {
    const totalPages = Math.ceil(total / pageSize) || 1;
    document.getElementById('page-info').textContent = `第 ${page} / ${totalPages} 页 (共 ${total} 条)`;
    document.getElementById('btn-prev-page').disabled = (page <= 1);
    document.getElementById('btn-next-page').disabled = (page >= totalPages);
}

/**
 * 用途说明：启动异步扫描任务。
 * 入参说明：无。
 * 返回值说明：无。
 */
async function startScanTask() {
    try {
        const response = await Request.post('/api/file_repository/scan', {}, {}, true);
        if (response.status === 'success') {
            Toast.show('索引任务已启动');
            resetProgressUI(); // 开始扫描前重置进度条
            enterScanningState();
        } else {
            Toast.show(response.msg);
        }
    } catch (error) {
        Toast.show('启动失败');
    }
}

/**
 * 用途说明：请求终止扫描任务。
 * 入参说明：无。
 * 返回值说明：无。
 */
async function stopScanTask() {
    if (!confirm('确定要终止当前的索引任务吗？')) return;
    try {
        await Request.post('/api/file_repository/stop', {}, {}, true);
        Toast.show('正在停止任务...');
    } catch (error) {
        Toast.show('请求停止失败');
    }
}

/**
 * 用途说明：进入扫描监控状态（启动轮询）。
 * 入参说明：无。
 * 返回值说明：无。
 */
function enterScanningState() {
    toggleUIByScanStatus(true);
    if (!scanInterval) {
        scanInterval = setInterval(checkScanProgress, 2000);
    }
}

/**
 * 用途说明：向后端查询扫描进度并更新 UI。
 * 入参说明：无。
 * 返回值说明：无。
 */
async function checkScanProgress() {
    try {
        const response = await Request.get('/api/file_repository/progress', {}, false);
        if (response.status === 'success') {
            const { status, progress } = response.data;
            
            if (status === 'scanning') {
                enterScanningState();
                updateProgressUI(progress);
            } else {
                if (scanInterval) {
                    clearInterval(scanInterval);
                    scanInterval = null;
                }
                toggleUIByScanStatus(false);
                
                if (status === 'completed') {
                    loadFileList(1);
                }
            }
        }
    } catch (error) {
        console.error('获取进度失败:', error);
    }
}

/**
 * 用途说明：根据扫描状态切换行区域的显示与隐藏。
 * 入参说明：isScanning (boolean) - 是否正在扫描。
 * 返回值说明：无。
 */
function toggleUIByScanStatus(isScanning) {
    const scanningRow = document.getElementById('scanning-row');
    const normalRow = document.getElementById('normal-row');
    
    if (isScanning) {
        scanningRow.style.display = 'flex';
        normalRow.style.display = 'none';
    } else {
        scanningRow.style.display = 'none';
        normalRow.style.display = 'flex';
    }
}

/**
 * 用途说明：更新进度条宽度和描述文本。
 * 入参说明：progress (object) - 进度数据对象。
 * 返回值说明：无。
 */
function updateProgressUI(progress) {
    const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
    const bar = document.getElementById('scan-progress-bar');
    const text = document.getElementById('scan-status-text');
    
    bar.style.width = percent + '%';
    text.textContent = `进度: ${percent}% (${progress.current}/${progress.total}) - ${progress.current_file}`;
}

/**
 * 用途说明：重置进度条 UI。
 * 入参说明：无。
 * 返回值说明：无。
 */
function resetProgressUI() {
    const bar = document.getElementById('scan-progress-bar');
    const text = document.getElementById('scan-status-text');
    if (bar) bar.style.width = '0%';
    if (text) text.textContent = '正在准备...';
}
