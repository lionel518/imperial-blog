import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from telegram.ext import Application

# 基础配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# 确保此 ID 与你频道一致，公开频道用 @username，私有用数字 ID
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL', '@FreePeriodical') 
BASE_DIR = Path(__file__).parent.parent
BLOG_POSTS_DIR = BASE_DIR / 'src' / 'content' / 'blog'
IMAGE_ASSETS_DIR = BASE_DIR / 'public' / 'assets' / 'blog'

def create_post(title, content, date, msg_id, image_rel_path=None):
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_POSTS_DIR / f"{msg_id}.md"
    
    # 修复：确保内容中的双引号不会破坏 Frontmatter
    safe_title = title.replace('"', '\\"')
    
    post_content = f"""---
title: "{safe_title}"
pubDatetime: {date.isoformat()}
description: "{safe_title}"
heroImage: "{image_rel_path if image_rel_path else ''}"
tags: ["自动同步"]
---

{content}
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(post_content)
    logger.info(f"📄 文章已生成: {msg_id}.md")

async def sync_channel():
    if not BOT_TOKEN: return False
    
    app = Application.builder().token(BOT_TOKEN).build()
    await app.initialize()
    
    try:
        # 核心：获取 Bot 最近收到的消息更新
        updates = await app.bot.get_updates()
        
        if not updates:
            logger.info("倒霉，暂时没发现新消息。请确保 Bot 是频道管理员且刚发过贴。")
            return True

        for update in updates:
            # 兼容频道帖子 (channel_post)
            msg = update.channel_post or update.message
            if not msg: continue

            # 1. 提取完整内容 (优先取 caption，若无则取 text)
            full_content = msg.caption if msg.caption else msg.text
            if not full_content: continue
            
            # 2. 提取标题 (第一行)
            title = full_content.split('\n')[0][:60]
            msg_id = msg.message_id
            
            # 3. 处理图片下载
            image_rel_path = ""
            if msg.photo:
                IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                photo_file = await app.bot.get_file(msg.photo[-1].file_id)
                img_name = f"{msg_id}.jpg"
                await photo_file.download_to_drive(custom_path=IMAGE_ASSETS_DIR / img_name)
                image_rel_path = f"/assets/blog/{img_name}"
                logger.info(f"📸 图片已同步: {img_name}")

            # 4. 创建 Markdown
            create_post(title, full_content, msg.date, msg_id, image_rel_path)

        return True
    except Exception as e:
        logger.error(f"同步出错: {e}")
        return False
    finally:
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(sync_channel())


