import os
import json
import requests
import logging
from datetime import datetime
from pathlib import Path

# 基础配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL', '@QiKan2026')
BASE_DIR = Path(__file__).parent.parent
BLOG_POSTS_DIR = BASE_DIR / 'src' / 'content' / 'blog'
IMAGE_ASSETS_DIR = BASE_DIR / 'public' / 'assets' / 'blog'
STATE_FILE = BASE_DIR / 'scripts' / 'sync_state.json'
API_BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'


def api_call(method, **params):
    """直接调用 Telegram Bot API"""
    url = f'{API_BASE}/{method}'
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    if not data.get('ok'):
        logger.error(f"API error: {data}")
        return None
    return data.get('result')


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'last_message_id': 0}


def save_state(last_message_id):
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_message_id': int(last_message_id)}, f)
    logger.info(f"✅ 已保存同步状态: last_message_id={last_message_id}")


def convert_entities_to_markdown(text, entities):
    """将 Telegram 消息实体转换为 Markdown 格式"""
    if not entities or not text:
        return text

    sorted_entities = sorted(entities, key=lambda e: e.get('offset', 0), reverse=True)
    result = text

    for entity in sorted_entities:
        offset = entity.get('offset', 0)
        length = entity.get('length', 0)
        entity_type = entity.get('type', '')
        url = entity.get('url', '')

        if offset < 0 or offset + length > len(text):
            continue

        entity_text = text[offset:offset + length]

        if entity_type == 'text_link' and url:
            result = result[:offset] + f'[{entity_text}]({url})' + result[offset + length:]
        elif entity_type == 'url':
            result = result[:offset] + entity_text + result[offset + length:]
        elif entity_type == 'bold':
            result = result[:offset] + f'**{entity_text}**' + result[offset + length:]
        elif entity_type == 'italic':
            result = result[:offset] + f'*{entity_text}*' + result[offset + length:]
        elif entity_type == 'underline':
            result = result[:offset] + f'**{entity_text}**' + result[offset + length:]
        elif entity_type == 'strikethrough':
            result = result[:offset] + f'~~{entity_text}~~' + result[offset + length:]
        elif entity_type == 'spoiler':
            result = result[:offset] + f'||{entity_text}||' + result[offset + length:]
        elif entity_type == 'code':
            result = result[:offset] + f'`{entity_text}`' + result[offset + length:]
        elif entity_type == 'pre':
            lang = entity.get('language', '')
            result = result[:offset] + f'```{lang}\n{entity_text}\n```' + result[offset + length:]
        elif entity_type == 'hashtag':
            tag_name = entity_text.lstrip('#')
            tag_slug = tag_name.lower().replace(' ', '-')
            result = result[:offset] + f'[{entity_text}](/tags/{tag_slug})' + result[offset + length:]
        elif entity_type == 'email':
            result = result[:offset] + f'[{entity_text}](mailto:{entity_text})' + result[offset + length:]

    return result


def create_post(title, content, date_str, msg_id, image_rel_path=None):
    """创建 Markdown 文章文件"""
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_POSTS_DIR / f'{msg_id}.md'

    safe_title = title.replace('"', '\\"')[:60]
    desc_lines = content.split('\n')
    safe_desc = desc_lines[0][:150] if desc_lines else ''
    safe_desc = safe_desc.replace('"', '\\"')

    channel_username = CHANNEL_ID.lstrip('@')
    telegram_link = f'https://t.me/{channel_username}/{msg_id}'

    post_content = f"""---
title: "{safe_title}"
pubDatetime: {date_str}
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


def sync_channel():
    """同步 Telegram 频道消息到博客"""
    if not BOT_TOKEN:
        logger.error('❌ TELEGRAM_BOT_TOKEN 未设置')
        return False

    if not CHANNEL_ID:
        logger.error('❌ TELEGRAM_CHANNEL 未设置')
        return False

    state = load_state()
    last_synced_id = int(state.get('last_message_id', 0))
    logger.info(f'📍 上次同步到 message_id: {last_synced_id}')

    channel_username = CHANNEL_ID.lstrip('@')
    logger.info(f'📡 开始同步频道: @{channel_username}')

    # 验证频道可访问
    chat_info = api_call('getChat', chat_id=f'@{channel_username}')
    if not chat_info:
        logger.error(f'❌ 无法访问频道 @{channel_username}，请确认 Bot 是频道管理员')
        return False
    logger.info(f'📋 频道标题: {chat_info.get("title", "unknown")}')

    # 使用 getUpdates 获取频道消息（getChatHistory 需要 API 6.8+，此 bot 版本较旧）
    total_synced = 0
    new_last_id = last_synced_id

    while True:
        # getUpdates 返回所有未确认的更新，POST 方式（不是 GET）
        resp = requests.post(f'{API_BASE}/getUpdates', timeout=30)
        data = resp.json()
        if not data.get('ok'):
            logger.error(f'❌ getUpdates API 调用失败: {data}')
            break

        updates = data.get('result', [])
        if not updates:
            logger.info('📭 没有更多新消息')
            break

        logger.info(f'📦 本批获取到 {len(updates)} 条更新')

        # 筛选出频道帖子，并按 message_id 倒序（从新到旧）
        channel_posts = []
        for upd in updates:
            channel_post = upd.get('channel_post') or upd.get('edited_channel_post')
            if not channel_post:
                continue
            chat = channel_post.get('chat', {})
            chat_id = chat.get('id')
            # 匹配频道 ID（数字格式）
            if str(chat_id) == str(chat_info.get('id')):
                channel_posts.append(channel_post)

        if not channel_posts:
            logger.info('📭 本批没有频道帖子')
            break

        # 按 message_id 倒序：最新在前
        channel_posts.sort(key=lambda m: m.get('message_id', 0), reverse=True)

        # 处理每条消息（最新 -> 最旧）
        batch_newest_id = channel_posts[0].get('message_id', 0)
        batch_oldest_id = channel_posts[-1].get('message_id', 0)

        # 确认已读的 update_id，下次 getUpdates 只返回更新的
        max_update_id = max(upd.get('update_id', 0) for upd in updates)

        # 如果最旧消息 <= last_synced_id，说明整批都同步过了
        if batch_oldest_id <= last_synced_id:
            logger.info(f'  ⏭️ 本批最旧消息 {batch_oldest_id} <= 已同步 {last_synced_id}，跳过')
            # 确认这批更新已读，继续检查是否有新的
            resp = requests.post(f'{API_BASE}/getUpdates', timeout=30, data={'offset': max_update_id + 1})
            break

        logger.info(f'  📬 本批消息范围: {batch_newest_id} ~ {batch_oldest_id}')
        logger.info(f'  📬 确认 offset update_id: {max_update_id + 1}')

        for msg in channel_posts:
            msg_id = msg.get('message_id', 0)

            # 遇到已同步消息，停止
            if msg_id <= last_synced_id:
                logger.info(f'  ⏭️ 遇到已同步消息 {msg_id} <= {last_synced_id}，停止')
                break

            # 获取文字内容
            raw_content = msg.get('caption', '') or msg.get('text', '')
            has_content = bool(raw_content)
            logger.info(f'  📝 has_content={has_content} content_len={len(raw_content) if raw_content else 0}')

            # 转换实体
            entities = msg.get('caption_entities', []) or msg.get('entities', [])
            full_content = convert_entities_to_markdown(raw_content, entities) if has_content else ''

            # 提取标题
            title = raw_content.split('\n')[0][:60] if has_content else ''

            # 检查按钮
            reply_markup = msg.get('reply_markup')
            has_buttons = bool(reply_markup and reply_markup.get('inline_keyboard'))
            logger.info(f'  🔘 has_buttons={has_buttons}')
            if has_buttons:
                logger.info(f'  ⏭️ 跳过带按钮的帖子: message_id={msg_id}')
                continue

            # 下载图片
            image_rel_path = None
            photo = msg.get('photo')
            logger.info(f'  🖼️ has_photo={bool(photo)}')
            if photo:
                best_photo = photo[-1]
                file_id = best_photo.get('file_id')
                logger.info(f'  📥 正在下载图片 file_id={file_id}')
                if file_id:
                    IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                    img_name = f'{msg_id}.jpg'
                    file_resp = requests.get(
                        f'{API_BASE}/getFile',
                        params={'file_id': file_id},
                        timeout=30
                    )
                    file_data = file_resp.json()
                    if file_data.get('ok'):
                        file_path = file_data['result']['file_path']
                        file_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
                        img_data = requests.get(file_url, timeout=60).content
                        with open(IMAGE_ASSETS_DIR / img_name, 'wb') as img_f:
                            img_f.write(img_data)
                        image_rel_path = f'/assets/blog/{img_name}'
                        logger.info(f'  ✅ 图片下载成功: {img_name} size={len(img_data)}')
                    else:
                        logger.info(f'  ❌ getFile 失败: {file_data}')
            else:
                logger.info(f'  ⏭️ 跳过纯文字帖子 (无图片): message_id={msg_id}')
                continue

            # 日期
            date_ts = msg.get('date', 0)
            date_str = datetime.utcfromtimestamp(date_ts).strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f'  ✅ 准备创建文章: msg_id={msg_id} title={title[:20]}')

            create_post(title, full_content, date_str, msg_id, image_rel_path)
            new_last_id = msg_id
            total_synced += 1

        # 确认已读的 update_id，防止下次重复获取
        requests.post(f'{API_BASE}/getUpdates', timeout=30, data={'offset': max_update_id + 1})

    if total_synced > 0:
        save_state(new_last_id)
        logger.info(f'🎉 同步完成！新增 {total_synced} 篇文章，最新 message_id: {new_last_id}')
    else:
        logger.info('✅ 没有新消息需要同步')

    return True


if __name__ == '__main__':
    sync_channel()
