# 📂 File Manager System —— Your "Grand Butler" for Massive Resources

<div align="center">

[English]| [中文](README_zh.md) 

</div>

This is a **born-for-NAS**, lightweight, and high-performance file management system designed to handle tens of thousands of cluttered files. It not only helps you organize files neatly but also uses "black tech" to find duplicate images and videos that take up space.

---

## 🚀 Deployment

The image is published on GitHub Container Registry: `ghcr.io/xie87241203/file_manager_system`.

> **Port note**: The service inside the container always listens on port **5000**. The examples below use `-p 8080:5000` (host 8080 → container 5000), so the access URL is `http://localhost:8080`. You may change the host port, but the container port must stay 5000.

### Option 1: Docker CLI (fastest)

```bash
docker run -d \
  --name file-manager-system \
  -p 8080:5000 \
  -v $(pwd)/data:/app/data \
  -v /path/to/your/files:/file_repository \
  --restart unless-stopped \
  ghcr.io/xie87241203/file_manager_system:latest
```

- `$(pwd)/data`: creates a `data` folder in the current directory for persistent data (Linux/macOS); you can also use any absolute path, e.g. `/volume1/docker/file-manager/data` on a NAS.
- `/path/to/your/files`: replace with the folder you want to manage.
- Once running, open `http://localhost:8080` (or `http://NAS_IP:8080` on a NAS).

### Option 2: Docker Compose

Create a `docker-compose.yml`:

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

Start it with `docker compose up -d`.

### Option 3: Portainer (recommended for NAS)

Portainer deploys via a **Stack**, reusing the Compose content above:

1. Log in to Portainer and select your Environment.
2. Go to **Stacks** → **Add stack**.
3. Name it `file-manager-system`, choose **Web editor**, and paste the `docker-compose.yml` content above.
4. Change the `volumes` paths to **absolute paths** on your NAS, for example:
   - `/volume1/docker/file-manager/data:/app/data`
   - `/volume1/media:/file_repository`
5. Click **Deploy the stack** and wait for the image to pull and start.
6. Open `http://NAS_IP:8080`.

> If you prefer **Containers → Add container**: set Image to `ghcr.io/xie87241203/file_manager_system:latest`, map port `8080 → 5000`, and bind both the `/app/data` and `/file_repository` volumes.

> **Permission tip**: The container runs as UID `1000`. If it cannot write data or read files, make sure the mapped directories are writable by that UID, e.g. `chown -R 1000:1000 /volume1/docker/file-manager/data`.

---

## ✨ What can it do for you?

*   **Multi-language Support**: Support both **Chinese** and **English** interfaces.
*   **Build Index**: Build a file index by scanning the repository for fast searching.
*   **Media Preview**: Preview images and videos after generating thumbnails.
*   **File Deduplication**: Identify identical files and similar video/image content through MD5 and Perceptual Hashing (pHash) to find duplicates for you.

---

## 📖 How to get started?

1.  **Start and Login**: Open `http://localhost:8080` (or `http://NAS_IP:8080` on a NAS). Default account is `admin`, and the default password is `admin123`.
2.  **Security First**: After logging in, please be sure to change your username and password through the system settings.
3.  **Create a Repository**: Create a file repository from the repository dropdown at the top of the home page.
4.  **Set the Path**: In "System Settings → Repository Directory", add the file directory for that repository (e.g. `/file_repository`).
5.  **Scan**: Go to "File Repository" and click scan to build the file index.
6.  **Generate Previews**: Click "Generate Thumbnails" below, and the system will silently prepare preview images for you in the background.
7.  **Deduplicate**: Feeling like your hard drive is almost full? Run "File Deduplication" to delete all those useless "clones".

---

## ⚙️ Common Configuration (Mapping)

| Path in Container | Description | Suggestion |
| :--- | :--- | :--- |
| `/app/data` | Database, thumbnail cache, system config and logs | Must be mapped, otherwise data will be lost after restart |
| `/file_repository` | Your file repository (example mount point) | Map to the folder you want to manage, and add that path under "System Settings → Repository Directory" |

> Service port: the container always listens on `5000`; map it with `-p HOST_PORT:5000` (the examples use `8080:5000`).

---

## 🛠️ Tech Stack
*   **Backend**: Python 3.11 / Flask / Waitress (The robust heart)
*   **Frontend**: Native JS / CSS3 / HTML5 (The smooth experience)
*   **Deployment**: Docker (Worry-free installation)

---

## 📝 For Developers
If you want to participate in development, please read [AGENTS.md](./AGENTS.md) first, which contains our coding conventions.
