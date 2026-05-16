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


# 期刊类型与 archiveAnalysis 映射（用于自动生成原创描述）
ARCHIVE_ANALYSIS_MAP = {
    "经济学人": "本档案收录国际权威政经期刊文摘，深度解析全球政治经济格局、中外关系、国际贸易等重大议题，有助于把握世界发展脉络，适合学习研究参考。",
    "时代周刊": "本档案收录全球新闻时事期刊精华，涵盖国际政治、社会动态、文化娱乐等领域，提供多元视角的新闻分析，适合了解世界时事动态。",
    "科学": "本档案收录前沿科技学术期刊内容，报道最新科学研究成果、技术创新和学术进展，涵盖生物、物理、医学等学科，适合追踪科技前沿。",
    "欧洲商业评论": "本档案收录欧洲商业管理期刊精华，聚焦组织战略、领导力、创新趋势等商业议题，提供深度商业洞察，适合企业管理者和学习者参考。",
    "美食": "本档案收录生活美食期刊内容，涵盖烹饪技艺、餐饮文化、食材探索等主题，传递生活美学，适合热爱美食文化的人士。",
    "新闻周刊": "本档案收录国际新闻周刊精华，提供全球政治、经济、社会等领域的深度报道和分析，帮助读者了解国际时事动态。",
    "麦肯锡季刊": "本档案收录全球顶级商业管理期刊内容，聚焦战略咨询、管理创新、市场趋势等，提供专业商业洞察，适合企业决策者参考。",
    "哈佛商业评论": "本档案收录国际顶级商业管理期刊精华，涵盖战略、领导力、组织管理等议题，传播前沿管理理念，适合商业管理者学习。",
    "金融时报": "本档案收录全球权威财经媒体精华，报道国际金融、经济、市场动态，提供专业财经分析，适合投资者和经济学习者参考。",
    "第一财经周刊": "本档案收录本土财经商业期刊内容，聚焦中国市场、企业创新、消费趋势等，提供接地气的商业分析，适合了解中国经济动态。",
    "三联生活周刊": "本档案收录本土人文生活期刊精华，涵盖社会观察、文化生活、人物报道等领域，传递人文关怀，适合品质生活追求者。",
    "财新周刊": "本档案收录专业财经媒体内容，聚焦中国市场、金融动态、企业报道，提供深度财经分析，适合专业人士和投资者参考。",
    "新科学家": "本档案收录国际科技期刊内容，报道最新科学研究、技术创新和科技趋势，涵盖生物、物理、空间等领域，适合科技爱好者。",
    "财富": "本档案收录全球商业杂志精华，聚焦企业动态、市场趋势、领袖访谈等，提供商业趋势洞察，适合商业人士了解全球商情。",
    "福布斯": "本档案收录全球商业财经杂志内容，聚焦财富榜单、创业投资、商业趋势等，提供精英商业视角，适合创业者和投资者参考。",
    "大西洋月刊": "本档案收录国际思想类期刊精华，涵盖政治、文化、社会、思想等领域的深度论述，培养独立思考能力，适合知识阶层阅读。",
    "南方人物周刊": "本档案收录人物报道期刊精华，以人物视角切入社会现实，传递人文温度与时代精神，适合关注社会与人物的读者。",
    "读者文摘": "本档案收录综合性文摘期刊内容，涵盖人生哲理、情感故事、健康生活等领域，传递温暖与智慧，适合广泛读者群体。",
    "时尚芭莎": "本档案收录时尚生活方式期刊内容，涵盖服饰、美容、艺术等主题，引领潮流品味，适合追求生活品质的读者。",
    "巴伦周刊": "本档案收录专业投资期刊内容，聚焦金融市场、投资策略、经济展望，提供专业财经分析，适合投资者参考。",
    "外交事务": "本档案收录国际关系期刊精华，深度分析全球政治、外交、安全等重大议题，提供地缘政治视角，适合关注国际格局的读者。",
    "自然界": "本档案收录自然科普期刊内容，报道自然世界的神奇与美丽，涵盖动物、植物、生态等主题，适合热爱自然的读者。",
    "计算机世界": "本档案收录科技资讯期刊内容，聚焦信息技术、互联网、软件开发等领域，追踪科技行业动态，适合科技从业者。",
    "证券时报": "本档案收录证券金融媒体内容，聚焦资本市场、股票投资、市场分析，提供专业投资参考，适合金融投资者。",
    "中国企业家": "本档案收录商业人物期刊精华，聚焦中国企业成长、创业故事、商业领袖，传递企业家精神，适合创业者和商业人士。",
    "创业家": "本档案收录创业创新期刊内容，聚焦创业历程、商业模式、创新实践，传递创业精神和商业智慧，适合创业者参考。",
    "南方周末": "本档案收录深度新闻期刊精华，以调查报道和深度评论见长，传递独立声音和批判精神，适合关注社会真相的读者。",
    "世界博览": "本档案收录国际视野期刊内容，涵盖环球旅行、异国文化、世界遗产等主题，拓宽国际视野，适合热爱旅行和文化的读者。",
}

def get_archive_analysis(title):
    """根据标题自动提取期刊类型并返回对应的 archiveAnalysis 描述"""
    for pub_type, analysis in ARCHIVE_ANALYSIS_MAP.items():
        if pub_type in title:
            return analysis
    # 默认描述（未匹配的期刊类型）
    return "本档案收录优质期刊文摘，内容涵盖政治、经济、科技、文化等领域，适合学习研究参考。"


def create_post(title, content, date_str, msg_id, image_rel_path=None):
    """创建 Markdown 文章文件"""
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_POSTS_DIR / f'{msg_id}.md'

    safe_title = title.replace('"', '\\"')[:60]
    desc_lines = content.split('\n')
    safe_desc = desc_lines[0][:150] if desc_lines else ''
    safe_desc = safe_desc.replace('"', '\\"')

    # 自动生成 archiveAnalysis
    archive_analysis = get_archive_analysis(title)

    channel_username = CHANNEL_ID.lstrip('@')
    telegram_link = f'https://t.me/{channel_username}/{msg_id}'

    post_content = f"""---
title: "{safe_title}"
pubDatetime: {date_str}
description: "{safe_desc}"
archiveAnalysis: "{archive_analysis}"
heroImage: "{image_rel_path if image_rel_path else ''}"
tags: ["自动同步"]
---

{content}

---
📌 [查看 Telegram 频道原文]({telegram_link})
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(post_content)
    logger.info(f"📄 文章已生成: {msg_id}.md -> {safe_title[:30]}, archiveAnalysis 已添加")


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
