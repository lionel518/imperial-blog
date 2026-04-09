import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from telegram.ext import Application
from telegram import MessageEntity

# 基础配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# 确保此 ID 与你频道一致，公开频道用 @username，私有用数字 ID
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL', '@FreePeriodical') 
BASE_DIR = Path(__file__).parent.parent
BLOG_POSTS_DIR = BASE_DIR / 'src' / 'content' / 'blog'
IMAGE_ASSETS_DIR = BASE_DIR / 'public' / 'assets' / 'blog'

def convert_entities_to_markdown(text: str, entities: list[MessageEntity]) -> str:
    """将 Telegram 消息实体转换为 Markdown 格式"""
    if not entities:
        logger.info(f"⚠️ 没有找到消息实体，原始文本: {repr(text[:200])}")
        return text
    
    logger.info(f"✅ 找到 {len(entities)} 个消息实体:")
    for i, entity in enumerate(entities):
        entity_text = text[entity.offset:entity.offset+entity.length] if entity.offset + entity.length <= len(text) else "[TEXT_OUT_OF_RANGE]"
        logger.info(f"  [{i}] type={entity.type}, offset={entity.offset}, length={entity.length}, text={repr(entity_text)}")
        if hasattr(entity, 'url') and entity.url:
            logger.info(f"      url={repr(entity.url)}")
    
    # 按偏移量从后往前处理，避免修改文本后影响后续偏移量
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)
    
    result = text
    for entity in sorted_entities:
        start = entity.offset
        end = start + entity.length
        
        # 安全检查：确保偏移量在文本范围内
        if start < 0 or end > len(text):
            logger.warning(f"⚠️ 实体偏移量超出范围: offset={start}, length={entity.length}, text_len={len(text)}")
            continue
            
        entity_text = text[start:end]
        
        if entity.type == MessageEntity.TEXT_LINK:
            # 文本链接：[显示文本](URL)
            if hasattr(entity, 'url') and entity.url:
                markdown = f"[{entity_text}]({entity.url})"
                result = result[:start] + markdown + result[end:]
                logger.info(f"✓ 处理 TEXT_LINK: {repr(entity_text)} -> {repr(markdown)}")
        elif entity.type == MessageEntity.URL:
            # 纯 URL：直接保留
            markdown = entity_text
            result = result[:start] + markdown + result[end:]
            logger.info(f"✓ 处理 URL: {repr(entity_text)}")
        elif entity.type == MessageEntity.BOLD:
            markdown = f"**{entity_text}**"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.ITALIC:
            markdown = f"*{entity_text}*"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.UNDERLINE:
            # Markdown 没有原生下划线，用 HTML 或粗体代替
            markdown = f"**{entity_text}**"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.STRIKETHROUGH:
            markdown = f"~~{entity_text}~~"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.SPOILER:
            markdown = f"||{entity_text}||"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.CODE:
            markdown = f"`{entity_text}`"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.PRE:
            # 代码块，检查是否有语言
            lang = entity.language if hasattr(entity, 'language') and entity.language else ""
            markdown = f"```{lang}\n{entity_text}\n```"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.MENTION:
            # @提及，直接保留
            pass
        elif entity.type == MessageEntity.HASHTAG:
            # #话题标签，链接到标签页
            tag_name = entity_text.lstrip('#')  # 去掉 # 号
            tag_slug = tag_name.lower().replace(' ', '-')  # 转换为 slug
            markdown = f"[{entity_text}](/tags/{tag_slug})"
            result = result[:start] + markdown + result[end:]
            logger.info(f"✓ 处理 HASHTAG: {repr(entity_text)} -> {repr(markdown)}")
        elif entity.type == MessageEntity.EMAIL:
            # 邮箱，用 mailto 链接
            markdown = f"[{entity_text}](mailto:{entity_text})"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.PHONE_NUMBER:
            # 电话号码，用 tel 链接
            markdown = f"[{entity_text}](tel:{entity_text})"
            result = result[:start] + markdown + result[end:]
    
    logger.info(f"📝 最终转换结果（前300字符）: {repr(result[:300])}")
    return result

def create_post(title, content, date, msg_id, image_rel_path=None):
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_POSTS_DIR / f"{msg_id}.md"
    
    # 修复：确保内容中的双引号不会破坏 Frontmatter
    safe_title = title.replace('"', '\\"')
    
    # 构建 Telegram 原文链接
    if not CHANNEL_ID:
        channel_username = "FreePeriodical"
    else:
        channel_username = CHANNEL_ID.lstrip('@') if CHANNEL_ID.startswith('@') else CHANNEL_ID
    # 确保 channel_username 不为空
    if not channel_username:
        channel_username = "FreePeriodical"
    telegram_link = f"https://t.me/{channel_username}/{msg_id}"
    
    post_content = f"""---
title: "{safe_title}"
pubDatetime: {date.isoformat()}
description: "{safe_title}"
heroImage: "{image_rel_path if image_rel_path else ''}"
tags: ["自动同步"]
---

{content}

---
📌 [查看 Telegram 频道原文]({telegram_link})
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

            logger.info(f"📨 收到消息: message_id={msg.message_id}, date={msg.date}")
            logger.info(f"   消息类型: {'channel_post' if update.channel_post else 'message'}")

            # 1. 提取完整内容 (优先取 caption，若无则取 text)
            raw_content = msg.caption if msg.caption else msg.text
            if not raw_content:
                logger.warning("⚠️ 消息内容为空，跳过")
                continue
            
            logger.info(f"📝 原始内容（前200字符）: {repr(raw_content[:200])}")
            
            # 2. 获取实体并转换为 Markdown
            entities = msg.caption_entities if msg.caption else msg.entities
            logger.info(f"🔍 实体来源: {'caption_entities' if msg.caption else 'entities'}")
            
            full_content = convert_entities_to_markdown(raw_content, entities)
            
            # 3. 提取标题 (第一行)
            title = raw_content.split('\n')[0][:60]
            msg_id = msg.message_id
            
            # 4. 处理图片下载
            image_rel_path = ""
            if msg.photo:
                IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                photo_file = await app.bot.get_file(msg.photo[-1].file_id)
                img_name = f"{msg_id}.jpg"
                await photo_file.download_to_drive(custom_path=IMAGE_ASSETS_DIR / img_name)
                image_rel_path = f"/assets/blog/{img_name}"
                logger.info(f"📸 图片已同步: {img_name}")
            else:
                logger.info(f"⏭️ 跳过纯文字帖子 (无图片): message_id={msg_id}")
                continue

            # 5. 创建 Markdown
            create_post(title, full_content, msg.date, msg_id, image_rel_path)

        return True
    except Exception as e:
        logger.error(f"同步出错: {e}")
        return False
    finally:
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(sync_channel())


