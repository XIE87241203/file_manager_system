# 项目代码规范 (Project Coding Standards)

本规范旨在为 `file_manager_system` 项目提供统一的代码编写与协作标准，确保代码的可读性、可维护性和安全性。

## 0. 全局规则 (Global Rules)
- **沟通语言**: 与 AI 的交互及所有回复统一使用 **中文**。
- **代码注释**: 所有方法（包括后端 API、业务函数、前端 JS 函数等）必须添加中文注解：
    - **用途说明**: 描述方法的具体功能。
    - **入参说明**: 详述参数来源、类型及含义（如 API 的 Query/Body 参数）。
    - **返回值说明**: 详述返回值的结构及关键字段（如果存在返回值）。
    - **同步更新**: 代码逻辑变更时，必须立即更新注释，确保 100% 一致。
- **类型声明**: **声明变量时必须显式标注变量类型**（例如 Python 中的 `count: int = 0`）。
- **数据结构**: **能用数据类（如 Python 中的 `dataclass`）尽量不要用字典（`dict`）**，以增强类型的可追溯性和代码健壮性。
- **日志规范**: **严禁使用 `print()`**。必须使用 `backend/common/log_utils.py` 中的 `LogUtils` 类（`info`, `debug`, `error`）。
- **身份验证**: 除登录接口外，所有前后端交互必须通过 Token 验证。Token 存储于浏览器 Cookie，后端通过 `AuthManager` 校验。
- **工具调用**: AI 在执行修改任务时，必须正确调用 IDE 提供的工具方法（如 `write_file`, `replace_text`）来确保代码修改的准确性。

## 1. 目录结构与组织
- **`/backend`**: 后端逻辑（Python/Flask），按功能模块划分（如 `auth/`, `setting/`）。
- **`/frontend`**: 前端界面（HTML/JS/CSS），页面专用的 JS/CSS 与 HTML 同名且在同一目录下。
- **公用代码**: 后端位于 `backend/common/`，前端位于 `frontend/common/`。
- **配置文件**: 根目录 `requirements.txt` (依赖)、`config.py` (全局静态配置)；`backend/setting/setting.json` (业务配置)。

## 2. 后端开发规范 (Python)
- **命名规范**:
    - 与数据库直接交换数据的 model 必须以 **`DBModel`** 结尾。
    - 用作 API 返回的数据类必须以 **`Result`** 结尾。
    - 其他通用数据对象默认使用 **`Info`** 结尾。
- **类型提示**: 所有方法必须显式标注入参和返回值类型。
    - 示例：`def get_data(uid: str) -> dict:`
- **逻辑分层**: 
    - `main.py` 仅用于路由分发，禁止实现业务逻辑。
    - 业务逻辑必须封装在专用的业务类中（如 `FileService`），实现高内聚低耦合。
- **代码风格**: 遵循 PEP 8 规范。
- **API 设计**: 
    - RESTful 风格，返回统一的 JSON 格式（包含 `status` 字段）及正确的 HTTP 状态码。
- **配置管理**: 在 `Setting` 类中新增变量时，必须同步修改 `save_config` 方法。

## 3. 前端开发规范 (JS/HTML/CSS)
- **模块化模式 (Module Pattern)**: 严禁全局变量/函数。使用对象字面量组织代码：
    - `State`: 管理页面状态（分页、定时器等）。
    - `UIController`: DOM 缓存及渲染逻辑。
    - `API`: 封装异步请求（基于 `Request` 工具类）。
    - `App`: 入口，负责初始化与事件绑定。
- **工具类使用**: 
    - 请求：必须使用 `frontend/common/request.js`。
    - 提示：必须使用 `Toast.show()`。
    - 进度：长时任务必须调用 `UIComponents.showProgressBar`。
- **UI 交互约定**: 
    - 使用 `id` 绑定 JS 逻辑，`class` 绑定 CSS 样式。
    - 批量删除列表：复选框位于最右侧，支持点击行自动选中。
    - 选中反馈：选中行必须应用 `.selected-row` 样式。

## 4. 数据库说明
### 4.1 操作原则
- **物理删除**: 删除文件时同步清理 `file_index` 和 `duplicate_files`，禁止操作 `history_file_index`。
- **解耦**: `video_features` 和 `history_file_index` 与 `file_index` 无物理关联。

### 4.2 表结构摘要
- **`file_index`**: 当前有效文件索引（路径、MD5、缩略图等）。
- **`history_file_index`**: 历史记录，记录所有曾存在的文件及其删除时间。
- **`video_features`**: 视频指纹特征及属性。
- **`duplicate_groups` / `duplicate_files`**: 存储重复文件的分组标识与成员关联。

## 5. 安全与配置规范
- **安全性**: 严禁明文存储密码，使用 SHA-256 哈希。防止路径穿越（如缩略图访问需校验基准路径）。
- **配置管理**: 全局静态配置统一存放在 `config.py` 的 `GlobalConfig` 类中。
