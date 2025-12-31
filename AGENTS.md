# 项目代码规范 (Project Coding Standards)

本规范旨在为 `file_manager_system` 项目提供统一的代码编写和协作标准，以确保代码的可读性、可维护性和安全性。

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

## 2. 后端开发规范 (Python)
- **组织结构**: 按照功能模块划分目录（例如 `backend/setting/`, `backend/auth/`）。
- **逻辑分层**: 
    - `main.py` 仅作为程序入口和路由分发器，**严禁在其中实现任何业务逻辑**。
    - 所有业务逻辑必须封装在对应模块（如 `backend/auth/`）的类或函数中。
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
- **前端代码结构**: 页面专用的 JS 和 CSS 储存在与 HTML 统一目录中，使用同一名字。
- **元素绑定约定**: 
    - **使用 `class` 绑定 CSS 样式**。
    - **使用 `id` 绑定 JavaScript 逻辑**（如获取 DOM 节点）。
- **前端公用代码**: 
    - 前端公用代码转移到 `frontend/common/` 目录下。
    - **样式复用**: 必须引入 `frontend/common/common.css` 以保持全局视觉风格统一（如卡片容器 `.card-container`、表单组 `.form-group`、主按钮 `.btn-primary` 等）。
    - **请求工具**: 必须使用 `frontend/common/request.js` 进行 API 调用。
    - **消息提示**: **严禁使用原生的 `alert()` 弹窗**。必须引入 `frontend/common/toast.js` 并使用 `Toast.show(message)` 进行交互提示。
    - **UI 组件复用**: **公用头部在 `frontend/common/ui_components.js` 中，如无特殊要求，默认引用此头部**。
        - 必须在 HTML 中包含 `<header class="top-bar"></header>` 占位符。
        - 必须在页面逻辑加载时调用 `UIComponents.initHeader(title, ...)` 方法动态初始化顶部工具栏，以确保全局导航和标题风格的一致性。
- **注释要求**: 遵循全局规则，所有 JS 函数必须包含中文注释。
- **前后端分离**: 前端仅负责 UI 展示与交互，通过 API 与后端通信。
- **API 地址配置**: 基础 API 地址通过登录页面的输入框动态指定，并存储在 `sessionStorage` 中。所有请求必须基于该地址。
- **Token 管理**: 登录成功后，前端必须将后端返回的 Token 存储在浏览器 Cookie 中（有效期 6 小时）。在后续调用除登录外的所有 API 时，必须在请求中携带该 Token。通常推荐使用封装好的 `Request` 工具类。

## 4. 安全与配置
- **安全性**: 
    - 严禁在代码或数据库中明文存储用户密码。
    - 后端验证应使用哈希值（目前项目采用 SHA-256）。
    - **会话安全**: 用户有且只有一个有效 Token，注销或重新登录会导致旧 Token 失效。Token 仅存储在内存中，不进行持久化。
