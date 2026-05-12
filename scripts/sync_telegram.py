import os
import re
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

    # 优先级 1: MESSAGE_ID 由 webhook workflow_dispatch 传入（实时触发模式）
    # 从该 message_id - 1 开始同步，触发后新消息都会被处理
    message_id = os.getenv('MESSAGE_ID')
    if message_id:
        last_synced_id = max(0, int(message_id) - 1)
        logger.info(f'🔔 Webhook 触发模式：从 message_id {last_synced_id + 1} 开始实时同步')

    # 优先级 2: BACKFILL_FROM 用于手动补全缺失图片
    backfill_from = os.getenv('BACKFILL_FROM')
    if backfill_from:
        last_synced_id = max(0, int(backfill_from) - 1)
        logger.info(f'🔧 补全模式：从 message_id {last_synced_id + 1} 开始重新拉取（仅补图片，已有的 .md 会跳过）')

    channel_username = CHANNEL_ID.lstrip('@')
    logger.info(f'📡 开始同步频道: @{channel_username}')

    # 验证频道可访问
    chat_info = api_call('getChat', chat_id=f'@{channel_username}')
    if not chat_info:
        logger.error(f'❌ 无法访问频道 @{channel_username}，请确认 Bot 是频道管理员')
        return False
    logger.info(f'📋 频道标题: {chat_info.get("title", "unknown")}')

    # 使用 getChatHistory 获取频道历史消息（不依赖未读状态，可任意获取历史）
    total_synced = 0
    new_last_id = last_synced_id
    offset_id = 0  # getChatHistory 用 message_id 分页，0 = 从最新开始
    limit_per_page = 100
    consecutive_skipped = 0  # 连续跳过的消息数（遇到已同步的消息时计数）

    while True:
        # getChatHistory: 从指定 offset_id 开始往前取 limit 条
        resp = api_call('getChatHistory', chat_id=chat_info.get('id'), message_id=offset_id, limit=limit_per_page)
        if not resp:
            logger.error('❌ getChatHistory API 调用失败')
            break

        messages = resp.get('messages', [])
        has_more = resp.get('has_more', False)

        if not messages:
            if not has_more:
                logger.info('📭 历史消息拉取完毕')
                break
            logger.info('📭 本页无消息，继续...')
            continue

        # getChatHistory 返回的消息是"从 offset_id 往前"的所有消息，最老的一条在 messages[-1]
        # 反转成从新到旧处理，方便去重和判断停止
        messages = list(reversed(messages))
        page_newest_id = messages[-1].get('message_id', 0) if messages else 0
        page_oldest_id = messages[0].get('message_id', 0) if messages else 0

        logger.info(f'  📬 本页消息范围: {page_newest_id} ~ {page_oldest_id} (共 {len(messages)} 条)')

        for msg in messages:
            msg_id = msg.get('message_id', 0)

            # 遇到已同步消息，记录并跳过，继续处理更旧的消息
            if msg_id <= last_synced_id:
                consecutive_skipped += 1
                continue

            # 重置跳过计数（遇到更新消息说明不是连续已同步）
            consecutive_skipped = 0

            # 获取文字内容
            raw_content = msg.get('caption', '') or msg.get('text', '')
            has_content = bool(raw_content)
            logger.info(f'  📝 msg_id={msg_id} has_content={has_content} content_len={len(raw_content) if raw_content else 0}')

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

            # 下载图片（BACKFILL 模式：图片缺失也重新下载）
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
                    img_path = IMAGE_ASSETS_DIR / img_name
                    # 图片已存在则跳过（除非是 BACKFILL 模式强制重下）
                    if img_path.exists() and not backfill_from:
                        image_rel_path = f'/assets/blog/{img_name}'
                        logger.info(f'  ⏭️ 图片已存在，跳过: {img_name}')
                    else:
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
                            with open(img_path, 'wb') as img_f:
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

            # 如果 .md 已存在，仅更新 heroImage（BACKFILL 模式）
            md_path = BLOG_POSTS_DIR / f'{msg_id}.md'
            if md_path.exists():
                existing_content = md_path.read_text(encoding='utf-8')
                if image_rel_path:
                    # 更新 heroImage
                    new_content = re.sub(
                        r'^heroImage:.*$',
                        f'heroImage: "{image_rel_path}"',
                        existing_content,
                        flags=re.MULTILINE
                    )
                    if new_content != existing_content:
                        md_path.write_text(new_content, encoding='utf-8')
                        logger.info(f'  🔄 更新已有文章的 heroImage: {msg_id}')
                else:
                    logger.info(f'  ⏭️ 已有文章，无图片，跳过: {msg_id}')
                new_last_id = msg_id
                total_synced += 1
            else:
                create_post(title, full_content, date_str, msg_id, image_rel_path)
                new_last_id = msg_id
                total_synced += 1

        if not has_more:
            logger.info('📭 已到达历史消息尽头')
            break

        # 继续拉取更旧的消息：用本页最老的消息 ID 作为下次 offset
        offset_id = page_oldest_id

    if total_synced > 0:
        if not os.getenv('DRY_RUN'):
            save_state(new_last_id)
            logger.info(f'🎉 同步完成！新增 {total_synced} 篇文章，最新 message_id: {new_last_id}')
        else:
            logger.info(f'🎉 同步完成（DRY_RUN）！处理 {total_synced} 篇，未更新 sync_state')
    else:
        logger.info('✅ 没有新消息需要同步')

    return True


if __name__ == '__main__':
    sync_channel()
