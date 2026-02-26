/**
 * 用途：新文件仓库页面逻辑
 */

const FileRepositoryNew = {
    /**
     * 页面状态管理
     */
    State: {
        allData: [], // 存储所有 100 条假数据
        pageSize: 15, // 每页显示数量
        currentPage: 1
    },

    /**
     * UI 控制器：DOM 缓存及渲染逻辑
     */
    UIController: {
        // DOM 元素缓存
        elements: {
            dataListBody: document.getElementById('data-list-body')
        },

        /**
         * 渲染数据列表
         * @param {Array} list - 数据列表
         */
        renderList: function(list) {
            const html = list.map(item => `
                <tr>
                    <td>${item.id}</td>
                    <td>${item.fileName}</td>
                    <td>${item.fileSize}</td>
                    <td>${item.updateTime}</td>
                    <td>
                        <button class="back-btn" style="padding: 2px 8px; font-size: 12px;">查看</button>
                    </td>
                    <td>这是一段备注信息，ID: ${item.id}</td>
                </tr>
            `).join('');

            this.elements.dataListBody.innerHTML = html;
        }
    },

    /**
     * 数据生成逻辑
     */
    DataService: {
        /**
         * 生成 100 条假数据
         * @returns {Array} 假数据列表
         */
        generateFakeData: function() {
            const data = [];
            for (let i = 1; i <= 100; i++) {
                data.push({
                    id: i,
                    fileName: `测试文件_${i}.dat`,
                    fileSize: (Math.random() * 100).toFixed(2) + ' MB',
                    updateTime: new Date().toLocaleString()
                });
            }
            return data;
        }
    },

    /**
     * 入口程序
     */
    App: {
        /**
         * 初始化
         */
        init: function() {
            console.log("FileRepositoryNew 模块初始化...");

            // 1. 初始化顶部工具栏
            HeaderToolbar.init({
                title: "新文件仓库",
                menuCallback: () => {
                    Toast.show("菜单功能开发中...");
                }
            });

            // 2. 生成假数据并初始化第一页
            FileRepositoryNew.State.allData = FileRepositoryNew.DataService.generateFakeData();
            this.updatePage(1);

            // 3. 绑定页面事件
            this.bindEvents();
        },

        /**
         * 更新页面内容（包含列表渲染和页码条更新）
         * @param {number} pageNum - 目标页码
         */
        updatePage: function(pageNum) {
            FileRepositoryNew.State.currentPage = pageNum;
            const start = (pageNum - 1) * FileRepositoryNew.State.pageSize;
            const end = start + FileRepositoryNew.State.pageSize;
            const pageData = FileRepositoryNew.State.allData.slice(start, end);

            // 渲染列表
            FileRepositoryNew.UIController.renderList(pageData);

            // 初始化/更新翻页栏
            PageBar.init({
                containerId: "pagination-container",
                totalItems: FileRepositoryNew.State.allData.length,
                pageSize: FileRepositoryNew.State.pageSize,
                currentPage: pageNum,
                onPageChange: (newPage) => {
                    this.updatePage(newPage);
                }
            });
        },

        /**
         * 绑定事件
         */
        bindEvents: function() {
            // 此处绑定页面主体相关的事件
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    FileRepositoryNew.App.init();
});
