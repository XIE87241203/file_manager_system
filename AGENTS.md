# 项目代码规范 (Project Coding Standards)

本规范旨在为 `file_manager_system` 项目提供统一的代码编写 and 协作标准，以确保代码的可读性、可维护性和安全性。

## 0. 全局规则 (Global Rules)
- **代码注释**: 所有方法（后端 Python 函数、前端 JavaScript 函数等）都必须添加中文注解。
    - 必须包含：**用途说明**。
    - 必须包含：**入参说明**。
    - 必须包含：**返回值说明**（如果存在返回值）。
- **沟通语言**: 与 AI 的交互及所有回复统一使用**中文**。

## 1. 目录结构规范
- **`/backend`**: 存放所有后端逻辑代码（基于 Python/Flask）。
- **`/frontend`**: 存放所有前端界面代码（HTML/JS/CSS）。
- **`requirements.txt`**: 位于根目录，记录项目所需的所有 Python 依赖项。
- **`config.py`**: 位于根目录，存储系统级全局静态配置。

## 2. 后端开发规范 (Python)
- **组织结构**: 按照功能模块划分目录（例如 `backend/setting/`, `backend/auth/`）。
- **类型提示 (Type Hinting)**: 
    - **所有 Python 方法必须显式注明入参类型和返回值类型**。
    - 示例：`def my_method(param1: str, param2: int) -> bool:`。
- **逻辑分层与封装**: 
    - `main.py` 仅作为程序入口 and 路由分发器，**严禁在其中实现 any 业务逻辑**。
    - **业务逻辑封装**: **复杂业务逻辑必须封装到专用的业务类中处理**（如 `AuthManager`, `FileManager`），严禁在路由函数中堆砌大量业务逻辑。
    - **低耦合高内聚**: 通过类 and 方法封装业务流程，减少代码间的耦合度和逻辑分散，提高可测试性和复用性。
- **代码风格**: 遵循 [PEP 8](https://peps.python.org/pep-0008/) 编程规范。
- **注释要求**: 遵循全局规则，使用 Docstring 格式。
- **日志规范**: **严禁使用 `print()` 打印信息**。必须使用 `backend/common/log_utils.py` 中的 `LogUtils` 类进行日志记录。
    - **`info`**: 记录重要的运行信息（如服务启动、用户登录、关键业务完成等）。
    - **`debug`**: 记录不重要的、仅在开发测试阶段用于排查问题的详细信息。
    - **`error`**: 记录程序运行中的异常、校验失败及错误信息。
- **API 设计**:
    - 统一采用 RESTful API 风格。
    - 响应数据必须为 JSON 格式，且包含明确的 `status` 字段。
    - 必须根据操作结果返回正确的 HTTP 状态码（如 200, 400, 401, 500 等）。
    - **身份验证**: 除了登录接口 (`/api/login`) 外，所有 API 接口都必须进行 Token 验证。后端应从请求（Header 或 JSON）中提取 Token 并通过 `AuthManager` 校验其有效性。
- **路径处理**: 考虑到模块化，必要时在入口文件（如 `main.py`）中使用 `sys.path.append` 处理跨目录导入。
- **后端公用代码**: 后端公用代码转移到`backend/common/`目录下。
- **后端配置管理**: 
    - 后端的通用配置提取到 `backend/setting/setting.json` 中统一管理。
    - **注意**：每当在 `Setting` 类中增加一个新的配置变量时，必须同步在 `save_config` 方法中添加相应的保存逻辑。

## 3. 前端开发规范
- **组织结构**: 按照功能模块划分目录（例如 `frontend/login/`）。
- **前端代码结构**: 
    - 页面专用的 JS 和 CSS 储存在与 HTML 统一目录中，且文件名保持一致（如 `file_repository.html`, `file_repository.js`, `file_repository.css`）。
    - HTML 底部脚本引入顺序：`ui_components.js` -> `request.js` -> `toast.js` -> 页面私有 JS。
- **JS 代码组织模式 (Module Pattern)**:
    - **严禁编写零散的全局变量和函数**。必须使用对象字面量将代码模块化，推荐结构如下：
        - `const State = { ... }`: 统一管理页面状态（如分页、搜索参数、定时器句柄等）。
        - `const UIController = { ... }`: 负责 DOM 元素缓存（`init` 方法中完成）及所有 UI 渲染逻辑（如 `renderTable`, `toggleLoading`）。
        - `const API = { ... }`: 封装所有与后端的异步请求（基于 `Request` 工具类）。
        - `const App = { ... }`: 程序的入口，负责初始化模块、绑定事件（`bindEvents`）及协调业务流程。
- **元素绑定约定**: 
    - **使用 `class` 绑定 CSS 样式**。
    - **使用 `id` 绑定 JavaScript 逻辑**（如获取 DOM 节点）。
- **前端公用代码**: 
    - **样式复用**: 必须引入 `frontend/common/common.css`。页面主容器推荐使用 `.repo-container` 或 `.card-container`。
    - **请求工具**: 必须使用 `frontend/common/request.js`。调用方式：`await Request.get(url, params, showLoading)`。
    - **消息提示**: 严禁使用原生 `alert()`。必须使用 `Toast.show(message)`。
    - **UI 组件复用**: 
        - 默认引用 `frontend/common/ui_components.js` 处理顶部工具栏（`initHeader`）。
        - 异步长时任务（如扫描、清理）必须调用 `UIComponents.showProgressBar` 展示全局进度条，并使用 `State` 中的定时器进行状态轮询。
- **布局与样式规范**:
    - **全屏布局**: 复杂管理页面推荐使用 `100vh`/`100vw` 布局，并设置 `overflow: hidden`，由内部容器（如 `.table-wrapper`）处理滚动。
    - **表格规范**: 
        - 表头推荐使用 `sticky` 定位以便在滚动时固定。
        - 支持排序的列需添加 `class="sortable"` 和 `data-field` 属性，并通过 JS 切换 `sort-asc` / `sort-desc` 样式。
        - **复选框交互**: 对于支持批量删除的列表，复选框列应放置在列表**最右侧**，且支持**点击行内容自动触发**对应复选框的选中/取消状态。
        - **选中行样式**: 选中的列表项/表格行必须应用公用样式 `.selected-row` 以提供视觉反馈。
- **注释要求**: 遵循全局规则。每个模块内部的方法必须包含：**用途说明**、**入参说明**、**返回值说明**。
- **前后端分离**: 前端仅负责 UI 展示与交互，所有数据通过 API 获取。
- **API 地址配置**: 基础 API 地址通过登录页面的输入框动态指定，并存储在 `sessionStorage` 中。
- **Token 管理**: 登录成功后存储在浏览器 Cookie 中（有效期 6 小时）。所有请求（除登录外）必须携带该 Token。

## 4. 数据库说明 (Database Documentation)
**注意：每当数据库表结构或操作原则发生变更时，必须同步修改本小节内容以保持文档与代码的一致性。**

### 4.1 数据表定义与操作原则
- **`file_index`**: 定义为当前有效的文件索引。记录最近一次完整扫描后仍存在于磁盘上的文件信息。
- **`history_file_index`**: 定义为文件索引历史。包含所有曾经被索引过的文件，即使该文件目前已从磁盘删除或在当前索引中被移除。
- **`video_features`**: 记录视频文件的特征指纹及相关属性，用于辅助视频去重逻辑。
- **`duplicate_groups`**: 存储重复文件检测后的分组标识。
- **`duplicate_files`**: 记录每个重复分组中包含的具体文件成员。
- **操作原则**:
    - 执行物理删除文件操作时，应同步清理 `file_index`，根据文件id清理`duplicate_files`，不能操作 `history_file_index`。
    - `video_features`和`history_file_index`与`file_index`无关联

### 4.2 具体表结构

#### 4.2.1 `file_index` (文件索引表)
- **用途**: 记录文件仓库下当前所有有效文件的基本信息及元数据。
- **字段说明**:
    - `id`: INTEGER, 主键, 自增。
    - `file_path`: TEXT, 文件绝对路径, 唯一约束 (UNIQUE)。
    - `file_md5`: TEXT, 文件 MD5 校验值, 唯一约束 (UNIQUE)。
    - `file_size`: INTEGER, 文件大小 (字节), 默认为 0。
    - `scan_time`: DATETIME, 扫描/更新时间, 默认为当前时间。
    - `thumbnail_path`: TEXT, 缩略图存储路径。
    - `is_in_recycle_bin`: INTEGER, 是否处于系统回收站 (0: 否, 1: 是), 默认为 0。

#### 4.2.2 `history_file_index` (历史文件索引表)
- **用途**: 记录所有曾经被索引的文件信息。
- **字段说明**:
    - `id`: INTEGER, 主键, 自增。
    - `file_path`: TEXT, 文件路径, 唯一约束。
    - `file_md5`: TEXT, 文件 MD5 值, 唯一约束。
    - `file_size`: INTEGER, 文件大小, 默认为 0。
    - `scan_time`: DATETIME, 原始扫描时间。
    - `delete_time`: DATETIME, 记录移入历史表的时间, 默认为当前时间。

#### 4.2.3 `video_features` (视频特征表)
- **用途**: 记录视频文件的特征指纹及相关属性，用于辅助视频去重逻辑。
- **字段说明**:
    - `id`: INTEGER, 主键, 自增。
    - `file_md5`: TEXT, 文件 MD5 值, 唯一约束。
    - `video_hashes`: TEXT, 视频指纹特征字符串, 唯一约束。
    - `duration`: REAL, 视频时长 (秒)。

#### 4.2.4 `duplicate_groups` (重复文件分组表)
- **用途**: 存储重复文件检测后的分组标识。
- **字段说明**:
    - `id`: INTEGER, 主键, 自增。
    - `group_id`: TEXT, 分组唯一标识符 (UUID 或 Hash), 唯一约束。

#### 4.2.5 `duplicate_files` (重复文件详情表)
- **用途**: 记录每个重复分组中包含的具体文件成员。
- **字段说明**:
    - `id`: INTEGER, 主键, 自增。
    - `group_id`: TEXT, 关联 `duplicate_groups` 表的 `group_id`。
    - `file_id`: INTEGER, 关联 `file_index` 表的 `id`, 唯一约束。

## 5. 安全与配置
- **安全性**: 
    - 严禁在代码或数据库中明文存储用户密码。
    - 后端验证应使用哈希值（目前项目采用 SHA-256）。
    - **会话安全**: 用户有且只有一个有效 Token，注销或重新登录会导致旧 Token 失效。Token 仅存储在内存中，不进行持久化。

## 6. 全局静态配置规范 (Global Static Configuration)
- **配置位置**: 根目录下的 `config.py` 文件。
- **管理方式**: 使用 `GlobalConfig` 静态类统一管理。
