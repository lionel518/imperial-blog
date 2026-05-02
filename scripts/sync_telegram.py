import os
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from telegram import MessageEntity
from telegram.ext import Application

# 基础配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL', '@QiKan2026')  # 默认 QiKan2026
BASE_DIR = Path(__file__).parent.parent
BLOG_POSTS_DIR = BASE_DIR / 'src' / 'content' / 'blog'
IMAGE_ASSETS_DIR = BASE_DIR / 'public' / 'assets' / 'blog'
STATE_FILE = BASE_DIR / 'scripts' / 'sync_state.json'


def load_state():
    """加载同步状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'last_message_id': 0}


def save_state(last_message_id):
    """保存同步状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_message_id': last_message_id}, f)
    logger.info(f"✅ 已保存同步状态: last_message_id={last_message_id}")


def convert_entities_to_markdown(text: str, entities: list[MessageEntity]) -> str:
    """将 Telegram 消息实体转换为 Markdown 格式"""
    if not entities:
        return text

    # 按偏移量从后往前处理，避免修改文本后影响后续偏移量
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)

    result = text
    for entity in sorted_entities:
        start = entity.offset
        end = start + entity.length

        if start < 0 or end > len(text):
            continue

        entity_text = text[start:end]

        if entity.type == MessageEntity.TEXT_LINK:
            if hasattr(entity, 'url') and entity.url:
                markdown = f"[{entity_text}]({entity.url})"
                result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.URL:
            markdown = entity_text
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.BOLD:
            markdown = f"**{entity_text}**"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.ITALIC:
            markdown = f"*{entity_text}*"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.UNDERLINE:
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
            lang = entity.language if hasattr(entity, 'language') and entity.language else ""
            markdown = f"```{lang}\n{entity_text}\n```"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.MENTION:
            pass
        elif entity.type == MessageEntity.HASHTAG:
            tag_name = entity_text.lstrip('#')
            tag_slug = tag_name.lower().replace(' ', '-')
            markdown = f"[{entity_text}](/tags/{tag_slug})"
            result = result[:start] + markdown + result[end:]
        elif entity.type == MessageEntity.EMAIL:
            markdown = f"[{entity_text}](mailto:{entity_text})"
            result = result[:start] + markdown + result[end:]

    return result


def create_post(title, content, date, msg_id, image_rel_path=None):
    """创建 Markdown 文章文件"""
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_POSTS_DIR / f"{msg_id}.md"

    # 安全处理标题中的双引号
    safe_title = title.replace('"', '\\"')

    # 生成 description（取前100字符或第一段）
    desc_lines = content.split('\n')
    safe_desc = desc_lines[0][:150] if desc_lines else ""
    safe_desc = safe_desc.replace('"', '\\"')

    # 构建 Telegram 原文链接
    channel_username = CHANNEL_ID.lstrip('@') if CHANNEL_ID.startswith('@') else CHANNEL_ID
    telegram_link = f"https://t.me/{channel_username}/{msg_id}"

    post_content = f"""---
title: "{safe_title}"
pubDatetime: {date.isoformat()}
description: "{safe_desc}"
heroImage: "{image_rel_path if image_rel_path else ''}"
tags: ["自动同步"]
---

{content}

---
📌 [查看 Telegram 频道原文]({telegram_link})
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(post_content)
    logger.info(f"📄 文章已生成: {msg_id}.md -> {safe_title[:30]}")


async def sync_channel():
    """同步 Telegram 频道消息到博客"""
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN 未设置")
        return False

    if not CHANNEL_ID:
        logger.error("❌ TELEGRAM_CHANNEL 未设置")
        return False

    app = Application.builder().token(BOT_TOKEN).build()
    await app.initialize()

    try:
        state = load_state()
        last_synced_id = state.get('last_message_id', 0)
        logger.info(f"📍 上次同步到 message_id: {last_synced_id}")

        # 获取频道 ID
        channel_username = CHANNEL_ID.lstrip('@')
        logger.info(f"📡 开始同步频道: @{channel_username}")

        # 使用 get_chat_history 主动获取频道消息
        offset_id = last_synced_id + 1  # 从上一条之后开始
        new_last_id = last_synced_id
        synced_count = 0

        # 分批获取，每次最多 100 条
        while True:
            updates = await app.bot.get_chat_history(
                chat_id=f"@{channel_username}",
                offset=offset_id,
                limit=100
            )

            if not updates:
                logger.info("📭 频道没有更多消息了")
                break

            logger.info(f"📦 本批获取到 {len(updates)} 条消息")

            for msg in updates:
                if msg.message_id <= last_synced_id:
                    continue

                # 获取消息内容
                raw_content = msg.caption if msg.caption else msg.text
                if not raw_content:
                    logger.info(f"⏭️ 跳过空消息: {msg.message_id}")
                    continue

                # 转换内容为 Markdown
                entities = msg.caption_entities if msg.caption else msg.entities
                full_content = convert_entities_to_markdown(raw_content, entities)

                # 提取标题
                title = raw_content.split('\n')[0][:60]

                # 处理图片
                image_rel_path = None
                if msg.photo:
                    IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                    photo_file = await app.bot.get_file(msg.photo[-1].file_id)
                    img_name = f"{msg.message_id}.jpg"
                    await photo_file.download_to_drive(custom_path=IMAGE_ASSETS_DIR / img_name)
                    image_rel_path = f"/assets/blog/{img_name}"
                    logger.info(f"📸 图片已下载: {img_name}")

                # 创建文章
                create_post(title, full_content, msg.date, msg.message_id, image_rel_path)
                new_last_id = msg.message_id
                synced_count += 1

            if len(updates) < 100:
                break

            # 继续获取下一批
            offset_id = updates[-1].message_id + 1

        if synced_count > 0:
            save_state(new_last_id)
            logger.info(f"🎉 同步完成！新增 {synced_count} 篇文章，最新 message_id: {new_last_id}")
        else:
            logger.info("✅ 没有新消息需要同步")

        return True

    except Exception as e:
        logger.error(f"❌ 同步出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await app.shutdown()


if __name__ == '__main__':
    asyncio.run(sync_channel())
