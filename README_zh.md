# 📂 文件管理系统 (File Manager System) —— 你的海量资源“大管家”

<div align="center">

[English](README.md) | [中文]

</div>

这是一个**为 NAS 而生**、轻量级、高性能的文件管理系统，专门用来对付成千上万的乱糟糟的文件。它不仅能帮你把文件整理得井井有条，还能通过“黑科技”帮你找出那些占地方的重复图片和视频。

---

## 🚀 部署教程

镜像发布在 GitHub Container Registry：`ghcr.io/xie87241203/file_manager_system`。

> **端口说明**：容器内服务固定监听 **5000** 端口。下面示例统一用 `-p 8080:5000`（宿主机 8080 → 容器 5000），访问地址为 `http://localhost:8080`。宿主机端口可按需修改，但容器侧端口必须保持 5000。

### 方式一：Docker CLI（最快）

```bash
docker run -d \
  --name file-manager-system \
  -p 8080:5000 \
  -v $(pwd)/data:/app/data \
  -v /path/to/your/files:/file_repository \
  --restart unless-stopped \
  ghcr.io/xie87241203/file_manager_system:latest
```

- `$(pwd)/data`：在当前目录创建 `data` 文件夹存放数据（Linux/macOS）；也可换成任意绝对路径，例如 NAS 上的 `/volume1/docker/file-manager/data`。
- `/path/to/your/files`：替换为你要管理的文件目录。
- 启动后浏览器访问 `http://localhost:8080`（NAS 部署则为 `http://NAS_IP:8080`）。

### 方式二：Docker Compose

新建 `docker-compose.yml`：

```yaml
services:
  file-manager-system:
    image: ghcr.io/xie87241203/file_manager_system:latest
    container_name: file-manager-system
    ports:
      - "8080:5000"
    volumes:
      - ./data:/app/data
      - /path/to/your/files:/file_repository
    restart: unless-stopped
```

执行 `docker compose up -d` 启动。

### 方式三：Portainer（推荐 NAS 用户）

Portainer 通过 **Stack** 部署，直接复用上面的 Compose 内容：

1. 登录 Portainer，进入目标环境（Environment）。
2. 左侧菜单 **Stacks** → **Add stack**。
3. 名称填 `file-manager-system`，构建方式选择 **Web editor**，粘贴上面的 `docker-compose.yml` 内容。
4. 将 `volumes` 中的路径改为 NAS 上的**绝对路径**，例如：
   - `/volume1/docker/file-manager/data:/app/data`
   - `/volume1/media:/file_repository`
5. 点击 **Deploy the stack**，等待镜像拉取并启动。
6. 浏览器访问 `http://NAS_IP:8080`。

> 若改用 **Containers → Add container** 手动创建：Image 填 `ghcr.io/xie87241203/file_manager_system:latest`，端口映射 `8080 → 5000`，并分别绑定 `/app/data` 与 `/file_repository` 两个卷。

> **权限提示**：容器以 UID `1000` 运行。若出现无法写入数据或读取文件的问题，请确保映射目录对该 UID 可读写，例如 `chown -R 1000:1000 /volume1/docker/file-manager/data`。

---

## ✨ 它能为你做什么？

*   **多语言支持**: 界面支持 **简体中文** 和 **英文** 切换。
*   **构建索引**: 通过扫描仓库构建文件索引，方便快速搜索。
*   **预览媒体**: 生成缩略图后能够预览图片和视频。
*   **文件查重**: 通过MD5和感知哈希 (pHash) 识别相同文件和内容相似的视频/图片，为你找出重复文件。

---

## 📖 怎么开始玩？

1.  **启动并登录**: 浏览器访问 `http://localhost:8080`（NAS 为 `http://NAS_IP:8080`）。默认账号为 `admin`，默认密码为 `admin123`。
2.  **安全第一**: 登录后，请务必通过系统设置修改你的用户名和密码。
3.  **创建仓库**: 在首页顶部的仓库下拉框中创建一个文件仓库。
4.  **填路径**: 在“系统设置”的“仓库目录”中为该仓库添加文件目录（如 `/file_repository`）。
5.  **扫一扫**: 进入“文件仓库”点一下扫描，构建文件索引。
6.  **造预览**: 点击“生成缩略图”，系统就会在后台默默为你准备预览图。
7.  **去重**: 感觉硬盘快满了？跑一遍“文件查重”，把那些没用的“分身”全删了。

> 🔑 **忘了管理员密码？别慌**：打开 `data/setting.json`（容器内为 `/app/data/setting.json`），把 `USER_DATA` 下的 `password` 字段改成一个新密码（直接写明文就行），保存后重启服务。系统会把初始管理员的密码重设为它，并自动把文件里的明文替换成密文。用新密码登录后，建议再到“系统设置 → 用户管理”里改一次密码。

---

## ⚙️ 常见配置 (映射关系)

| 容器内路径 | 它是干嘛的 | 建议 |
| :--- | :--- | :--- |
| `/app/data` | 数据库、缩略图缓存、系统配置与日志 | 必须映射，否则重启后数据会丢 |
| `/file_repository` | 文件库（示例挂载点） | 映射到你想管理文件的那个文件夹，并在“系统设置 → 仓库目录”中加入该路径 |

> 服务端口：容器内固定监听 `5000`，通过 `-p 宿主机端口:5000` 映射（示例用 `8080:5000`）。

---

## 🛠️ 技术栈
*   **后端**: Python 3.11 / Flask / Waitress (稳健的心脏)
*   **前端**: 原生 JS / CSS3 / HTML5 (丝滑的体验)
*   **部署**: Docker (省心的安装)

---

## 📝 开发者请看
如果你想参与开发，请务必先读读 [AGENTS.md](./AGENTS.md)，那里有我们的代码约定。
