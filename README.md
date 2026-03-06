# 📂 File Manager System —— Your "Grand Butler" for Massive Resources

<div align="center">

[English]| [中文](README_zh.md) 

</div>

This is a **born-for-NAS**, lightweight, and high-performance file management system designed to handle tens of thousands of cluttered files. It not only helps you organize files neatly but also uses "black tech" to find duplicate images and videos that take up space.

---

## 🚀 1-Minute Quick Start (Docker)

Want to experience it directly? Just run one command (remember to replace `xxx` with the path to the folder where you store files on your computer):

```bash
docker run -d \
  --name file-manager-system \
  -p 8080:8080 \
  -v ${pwd}/data:/app/data \
  -v xxx:/file_repository \
  ghcr.io/xie87241203/file_manager_system:latest
```

---

## ✨ What can it do for you?

*   **Multi-language Support**: Support both **Chinese** and **English** interfaces.
*   **Build Index**: Build a file index by scanning the repository for fast searching.
*   **Media Preview**: Preview images and videos after generating thumbnails.
*   **File Deduplication**: Identify identical files and similar video/image content through MD5 and Perceptual Hashing (pHash) to find duplicates for you.

---

## 📖 How to get started?

1.  **Start and Login**: Once the container is running, enter the address in your browser. Default account is `admin`, and the default password is `admin123`.
2.  **Security First**: After logging in, please be sure to change your username and password through the system settings.
3.  **Scan**: Fill in the path in "System Settings", then go to "File Repository" and click scan.
4.  **Generate Previews**: Click "Generate Thumbnails" below, and the system will silently prepare preview images for you in the background.
5.  **Deduplicate**: Feeling like your hard drive is almost full? Run "File Deduplication" to delete all those useless "clones".

---

## ⚙️ Common Configuration (Mapping)

| Path in Container | Description | Suggestion |
| :--- | :--- | :--- |
| `/app/data` | Stores database and cache | Must be mapped, otherwise data will be lost after restart |
| `/file_repository` | Your file repository | Map to the folder you want to manage |

---

## 🛠️ Tech Stack
*   **Backend**: Python 3.11 / Flask / Waitress (The robust heart)
*   **Frontend**: Native JS / CSS3 / HTML5 (The smooth experience)
*   **Deployment**: Docker (Worry-free installation)

---

## 📝 For Developers
If you want to participate in development, please read [AGENTS.md](./AGENTS.md) first, which contains our coding conventions.
