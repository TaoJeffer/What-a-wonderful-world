# 小红书图文科普知识自动发布工具

本目录包含一套使用 [Playwright](https://playwright.dev/python/) 自动登录小红书创作者中心、并发布图文科普知识帖子的 Python 脚本。

---

## 目录结构

```
xiaohongshu/
├── publish.py          # 主脚本：登录 + 发布
├── content.py          # 科普内容库（标题、正文、标签、图片）
├── requirements.txt    # Python 依赖
├── images/             # 存放待上传的本地图片
└── README.md           # 本文档
```

---

## 环境准备

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 准备图片（可选）

将图片放入 `images/` 目录，并在 `content.py` 中对应帖子的 `images` 字段填写相对路径（相对于 `xiaohongshu/` 目录）。

若图片不存在，脚本会自动生成占位符图片（安装了 Pillow 时带文字，否则为 1×1 白色图片）。

---

## 使用方法

### 二维码登录（默认，推荐）

```bash
cd xiaohongshu
python publish.py
```

脚本会打开浏览器并显示小红书登录页，使用手机 App 扫码即可完成登录，随后自动发布第一篇帖子（`content.py` 中 `POSTS[0]`）。

### 指定帖子编号

```bash
python publish.py --index 1   # 发布 POSTS[1]
python publish.py --index 2   # 发布 POSTS[2]
```

### 无头模式（服务器 / CI 环境）

```bash
python publish.py --headless
```

> **注意**：无头模式下二维码无法显示，建议先在有界面的环境完成一次扫码登录（Cookies 会缓存到 `.xhs_cookies.json`），之后即可复用缓存登录。

### 手机号 + 验证码登录

```bash
python publish.py --phone
# 或通过环境变量传入手机号
XHS_PHONE=13812345678 python publish.py --phone
```

---

## 添加新的科普内容

编辑 `content.py`，在 `POSTS` 列表中追加新的条目：

```python
{
    "title": "🔭 黑洞是什么？",
    "body": "黑洞是……",
    "tags": ["科普", "黑洞", "天文"],
    "images": ["images/black_hole.png"],
},
```

---

## 注意事项

* 本工具仅供学习与研究目的，请遵守[小红书用户协议](https://www.xiaohongshu.com/protocols/user-agreement)及相关法规。
* Cookies 文件（`.xhs_cookies.json`）包含登录凭证，已加入 `.gitignore`，请勿提交到代码仓库。
* 请勿频繁、批量发布，以免触发平台风控。
