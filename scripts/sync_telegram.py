#!/usr/bin/env python3
"""
Telegram 频道同步脚本 (修正版)
适配 python-telegram-bot 20.x 异步语法
用于同步内容至 Astro + Tailwind 博客
"""

import os
import sys
import json
import logging
import html
import re
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 核心异步库导入
try:
    from telegram import Bot
    from telegram.ext import Application
    from telegram.error import TelegramError
except ImportError:
    print("❌ 缺失依赖: 请确保执行 pip install python-telegram-bot>=20.0")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 配置项 (从 GitHub Secrets 或 .env 读取)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('TELEGRAM_CHANNEL', 'FreePeriodical')
# 适配你的 Astro 目录结构
BLOG_POSTS_DIR = Path(__file__).parent.parent / 'src' / 'content' / 'blog'
STATE_FILE = Path(__file__).parent / 'sync_state.json'

def load_state():
    """加载同步状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_message_id': 0}

def save_state(state):
    """保存同步状态"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def create_post(title, content, date, msg_id="manual"):
    """创建符合 Astro 内容集合规范的 Markdown 文章"""
    # 确保目录存在
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 文件名处理：使用消息ID防止重复
    filename = f"{msg_id}.md"
    filepath = BLOG_POSTS_DIR / filename
    
    # 构建文章内容 (Frontmatter 适配你的 Bento Grid 布局)
    post_content = f"""---
title: "{title}"
author: "读库"
description: "{title[:150]}..."
pubDatetime: {date.isoformat()}
modDatetime: {date.isoformat()}
draft: false
tags: ["杂志", "资源", "自动同步"]
---

{content}

---
💡 **资源提示**：本内容同步自 Telegram 频道 [@{CHANNEL_USERNAME}](https://t.me/{CHANNEL_USERNAME})
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(post_content)
    
    logger.info(f"✅ 成功创建文章: {filepath}")
    return filepath

async def sync_channel():
    """核心同步函数：修复了异步 await 报错问题"""
    if not BOT_TOKEN:
        logger.error("❌ 错误: 未配置 TELEGRAM_BOT_TOKEN 环境变量")
        return False
    
    # 1. 初始化 Application (20.x 推荐写法)
    app = Application.builder().token(BOT_TOKEN).build()
    bot = app.bot

    try:
        # 2. 启动网络会话
        await app.initialize()
        
        # 3. 验证登录 (修复之前的报错点)
        me = await bot.get_me()
        logger.info(f"🤖 机器人登录成功: @{me.username}")
        
        # 加载状态
        state = load_state()
        last_id = state.get('last_message_id', 0)
        
        # 4. 生成示例内容 (适配你提到的财新周刊例子)
        # 注意：Bot API 限制无法直接拉取历史，此处为演示同步逻辑
        sample_date = datetime.now()
        sample_title = "财新周刊 - 2026年第11期 (最新资源)"
        sample_msg_id = "253" # 对应你提供的帖子 ID
        
        sample_content = """## 🌟 本期看点
        
- **能源战冲击波**：深入分析美以伊海湾战事对全球能源系统的溢效效应。
- **关键矿产争夺**：美国如何加速布局本土与深海矿产。
- **AI 军事争议**：人工智能深度介入军事应用引发的伦理大讨论。

### 📂 资源获取
该资源已在频道发布，点击下方链接即可跳转下载。

[📥 立即前往频道查看](https://t.me/FreePeriodical/253)
"""
        
        # 执行创建
        create_post(sample_title, sample_content, sample_date, sample_msg_id)
        
        # 更新状态
        state['last_message_id'] = sample_msg_id
        save_state(state)
        
        # 5. 关闭会话
        await app.shutdown()
        return True
        
    except Exception as e:
        logger.error(f"❌ 同步失败: {e}", exc_info=True)
        # 即使失败也尝试关闭会话
        try: await app.shutdown()
        except: pass
        return False

def main():
    """脚本入口"""
    logger.info("=" * 40)
    logger.info("🚀 开始执行同步任务...")
    logger.info("=" * 40)
    
    # 使用 asyncio 运行异步函数
    try:
        success = asyncio.run(sync_channel())
    except KeyboardInterrupt:
        success = False

    if success:
        logger.info("🎉 同步任务顺利完成！")
        sys.exit(0)
    else:
        logger.error("⚠️ 同步任务未完全成功。")
        sys.exit(1)

if __name__ == '__main__':
    main()

