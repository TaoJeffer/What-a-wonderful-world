# -*- coding: utf-8 -*-
"""
xiaohongshu/publish.py
======================
使用 Playwright 自动登录小红书（PC 端创作者中心）并发布图文科普知识帖子。

用法
----
    # 安装依赖
    pip install -r requirements.txt
    playwright install chromium

    # 运行（扫码登录，发布第一条内容）
    python publish.py

    # 指定要发布的帖子编号（0-based index，参见 content.py）
    python publish.py --index 1

    # 无头模式（服务器环境）
    python publish.py --headless

环境变量（可选，用于手机号 + 验证码登录）
-----------------------------------------
    XHS_PHONE   : 手机号（如 13812345678）
    XHS_CODE    : 短信验证码（在脚本启动后手动填入，或由外部流程注入）

注意
----
* 默认使用扫码登录（二维码方式），无需填写账号密码。
* 本脚本仅用于学习与研究目的，请遵守小红书平台的使用条款。
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
CREATOR_URL = "https://creator.xiaohongshu.com"
LOGIN_URL = f"{CREATOR_URL}/login"
PUBLISH_URL = f"{CREATOR_URL}/publish/publish"

# 默认等待超时（毫秒）
DEFAULT_TIMEOUT = 60_000
# 登录二维码扫描等待超时（毫秒）
QR_TIMEOUT = 120_000

# Cookies 本地缓存路径（避免每次都要重新扫码）
COOKIES_FILE = Path(__file__).parent / ".xhs_cookies.json"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _generate_placeholder_images(post: dict, base_dir: Path) -> list[Path]:
    """
    如果 content.py 中指定的图片不存在，则生成简单的占位符 PNG 图片。
    返回实际存在的图片路径列表。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        _has_pillow = True
    except ImportError:
        _has_pillow = False

    existing: list[Path] = []
    for rel_path in post.get("images", []):
        img_path = base_dir / rel_path
        img_path.parent.mkdir(parents=True, exist_ok=True)
        if not img_path.exists():
            if _has_pillow:
                _create_placeholder_with_pillow(img_path, post["title"])
            else:
                _create_minimal_png(img_path)
            log.info("已生成占位图片: %s", img_path)
        existing.append(img_path)
    return existing


def _create_placeholder_with_pillow(path: Path, title: str) -> None:
    """用 Pillow 创建带文字的占位图片。"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1080, 1080), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    # 简单绘制标题文字（不依赖特定字体）
    draw.text((80, 480), title, fill=(50, 50, 50))
    img.save(path, "PNG")


def _create_minimal_png(path: Path) -> None:
    """不依赖 Pillow，写入一个最小合法的 1×1 白色 PNG 文件。"""
    import base64

    # 预生成的 1×1 白色 PNG（base64 编码）
    minimal_png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
        "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
    )
    path.write_bytes(base64.b64decode(minimal_png_b64))


def _load_cookies(context) -> bool:
    """从本地文件加载 Cookies；如果文件不存在则返回 False。"""
    if not COOKIES_FILE.exists():
        return False
    import json

    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    context.add_cookies(cookies)
    log.info("已从 %s 加载 Cookies", COOKIES_FILE)
    return True


def _save_cookies(context) -> None:
    """将当前 Cookies 保存到本地文件以便复用。"""
    import json

    cookies = context.cookies()
    COOKIES_FILE.write_text(
        json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("Cookies 已保存到 %s", COOKIES_FILE)


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------

def login_with_qr(page) -> None:
    """打开登录页，等待用户扫描二维码完成登录。"""
    log.info("正在打开登录页面: %s", LOGIN_URL)
    page.goto(LOGIN_URL, timeout=DEFAULT_TIMEOUT)

    # 点击"二维码登录"选项卡（如果页面默认不是二维码登录）
    try:
        qr_tab = page.locator("text=二维码登录").first
        qr_tab.click(timeout=5_000)
    except PlaywrightTimeoutError:
        pass  # 已经是二维码登录状态，忽略

    log.info("请在 %d 秒内使用小红书 App 扫描页面上的二维码…", QR_TIMEOUT // 1000)

    # 等待登录成功后跳转到创作者中心首页
    page.wait_for_url(f"{CREATOR_URL}/**", timeout=QR_TIMEOUT)
    log.info("登录成功！当前 URL: %s", page.url)


def login_with_phone(page, phone: str) -> None:
    """使用手机号 + 短信验证码登录（需要在终端手动输入验证码）。"""
    log.info("正在打开登录页面: %s", LOGIN_URL)
    page.goto(LOGIN_URL, timeout=DEFAULT_TIMEOUT)

    # 切换到手机号登录
    try:
        phone_tab = page.locator("text=手机号登录").first
        phone_tab.click(timeout=5_000)
    except PlaywrightTimeoutError:
        pass

    phone_input = page.locator("input[placeholder*='手机号']").first
    phone_input.fill(phone)

    send_btn = page.locator("text=发送验证码").first
    send_btn.click()

    code = input("请输入短信验证码: ").strip()
    code_input = page.locator("input[placeholder*='验证码']").first
    code_input.fill(code)

    login_btn = page.locator("button:has-text('登录')").first
    login_btn.click()

    page.wait_for_url(f"{CREATOR_URL}/**", timeout=DEFAULT_TIMEOUT)
    log.info("登录成功！当前 URL: %s", page.url)


def publish_post(page, post: dict, image_paths: list[Path]) -> None:
    """
    在小红书创作者中心发布一篇图文帖子。

    Parameters
    ----------
    page        : Playwright Page 对象
    post        : 来自 content.py 的帖子信息字典
    image_paths : 实际存在的本地图片路径列表
    """
    log.info("正在打开发布页面: %s", PUBLISH_URL)
    page.goto(PUBLISH_URL, timeout=DEFAULT_TIMEOUT)

    # ── 1. 上传图片 ──────────────────────────────────────────────────────
    log.info("正在上传图片: %s", [str(p) for p in image_paths])
    upload_input = page.locator("input[type='file']").first
    upload_input.set_input_files([str(p) for p in image_paths])

    # 等待图片上传完成（缩略图出现）
    page.wait_for_selector(".image-item, .upload-item, .img-item", timeout=30_000)
    log.info("图片上传完成")

    # ── 2. 填写标题 ──────────────────────────────────────────────────────
    title_input = page.locator("input[placeholder*='标题']").first
    title_input.fill(post["title"])
    log.info("已填写标题: %s", post["title"])

    # ── 3. 填写正文 ──────────────────────────────────────────────────────
    body_editor = page.locator(
        ".ql-editor, [contenteditable='true'], textarea[placeholder*='内容']"
    ).first
    body_editor.click()
    body_editor.fill(post["body"])
    log.info("已填写正文（%d 字）", len(post["body"]))

    # ── 4. 添加话题标签 ──────────────────────────────────────────────────
    for tag in post.get("tags", []):
        try:
            tag_input = page.locator(
                "input[placeholder*='话题'], input[placeholder*='标签']"
            ).first
            tag_input.fill(f"#{tag}")
            time.sleep(0.5)
            # 选择第一个建议项
            suggestion = page.locator(".topic-item, .tag-item").first
            suggestion.click(timeout=3_000)
            log.info("已添加标签: #%s", tag)
        except PlaywrightTimeoutError:
            log.warning("未能添加标签 #%s（可能已存在或选择器失效）", tag)

    # ── 5. 点击发布按钮 ──────────────────────────────────────────────────
    publish_btn = page.locator(
        "button:has-text('发布'), button:has-text('提交')"
    ).last
    publish_btn.click()
    log.info("已点击发布按钮，等待发布完成…")

    # 等待发布成功提示
    try:
        page.wait_for_selector(
            "text=发布成功, text=已发布, .success-toast",
            timeout=30_000,
        )
        log.info("🎉 发布成功！")
    except PlaywrightTimeoutError:
        log.warning("未检测到发布成功提示，请手动确认帖子是否已发布。")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="自动登录小红书并发布图文科普知识帖子"
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="要发布的帖子编号（参见 content.py，0-based，默认 0）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式运行浏览器（适用于服务器环境）",
    )
    parser.add_argument(
        "--phone",
        action="store_true",
        help="使用手机号 + 验证码登录（默认为二维码登录）",
    )
    args = parser.parse_args()

    # 导入内容配置
    sys.path.insert(0, str(Path(__file__).parent))
    from content import POSTS  # noqa: PLC0415

    if args.index >= len(POSTS):
        log.error("帖子编号 %d 超出范围（共 %d 篇）", args.index, len(POSTS))
        sys.exit(1)

    post = POSTS[args.index]
    base_dir = Path(__file__).parent
    image_paths = _generate_placeholder_images(post, base_dir)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()

        try:
            # ── 登录 ────────────────────────────────────────────────────
            if _load_cookies(context):
                # 尝试用缓存 Cookies 直接访问创作者中心
                page.goto(CREATOR_URL, timeout=DEFAULT_TIMEOUT)
                if page.url.startswith(CREATOR_URL) and "login" not in page.url:
                    log.info("Cookies 有效，无需重新登录")
                else:
                    log.info("Cookies 已过期，重新登录")
                    if args.phone:
                        phone = os.environ.get("XHS_PHONE") or input("请输入手机号: ").strip()
                        login_with_phone(page, phone)
                    else:
                        login_with_qr(page)
                    _save_cookies(context)
            else:
                if args.phone:
                    phone = os.environ.get("XHS_PHONE") or input("请输入手机号: ").strip()
                    login_with_phone(page, phone)
                else:
                    login_with_qr(page)
                _save_cookies(context)

            # ── 发布 ────────────────────────────────────────────────────
            publish_post(page, post, image_paths)

        except PlaywrightTimeoutError as exc:
            log.error("操作超时: %s", exc)
            sys.exit(1)
        except KeyboardInterrupt:
            log.info("用户中断操作")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
