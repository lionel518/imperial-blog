#!/usr/bin/env python3
"""
Telegram 频道同步脚本（Bot 版本 - 异步）
从 Telegram 频道获取内容并同步到博客
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

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    print("请安装依赖: pip install python-telegram-bot>=20.0")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 配置
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('TELEGRAM_CHANNEL', 'FreePeriodical')
BLOG_POSTS_DIR = Path(__file__).parent.parent / 'src' / 'data' / 'blog'
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


def escape_markdown(text):
    """转义 Markdown 特殊字符"""
    if not text:
        return ""
    # 简单的 HTML 到 Markdown 转换
    text = html.unescape(text)
    # 替换粗体
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    # 替换斜体
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    # 替换链接
    text = re.sub(r'<a href="(.*?)">(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)
    # 移除其他 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    return text


def extract_title(text):
    """从文本中提取标题"""
    if not text:
        return "无标题"
    
    # 取第一行作为标题
    lines = text.strip().split('\n')
    title = lines[0].strip()
    
    # 如果标题太长，截断
    if len(title) > 100:
        title = title[:97] + "..."
    
    # 如果第一行太短，取前两三个词
    if len(title) < 5:
        title = " ".join(text.split()[:5]) + "..."
    
    return title


def create_post(title, content, date, msg_id=None, tags=None):
    """创建博客文章"""
    if tags is None:
        tags = ['杂志', '资源']
    
    # 生成文件名（优先用消息ID，否则用标题）
    if msg_id:
        filename = f"{msg_id}.md"
    else:
        slug = re.sub(r'[^\w\-]', '', title.lower().replace(' ', '-'))[:50]
        date_str = date.strftime('%Y-%m-%d')
        filename = f"{date_str}-{slug}.md"
    
    filepath = BLOG_POSTS_DIR / filename
    
    # 防止重名
    counter = 1
    while filepath.exists():
        if msg_id:
            filename = f"{msg_id}-{counter}.md"
        else:
            filename = f"{date_str}-{slug}-{counter}.md"
        filepath = BLOG_POSTS_DIR / filename
        counter += 1
    
    # 确保目录存在
    BLOG_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 构建文章内容
    post_content = f"""---
title: "{title}"
author: 读库
description: "{title}"
pubDatetime: {date.isoformat()}
modDatetime: {date.isoformat()}
draft: false
tags: {tags}
---

{content}
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(post_content)
    
    logger.info(f"创建文章: {filepath}")
    return filepath


async def sync_channel():
    """同步频道内容"""
    if not BOT_TOKEN:
        logger.error("请配置 TELEGRAM_BOT_TOKEN 环境变量")
        return False
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # 测试连接
        me = await bot.get_me()
        logger.info(f"机器人登录成功: {me.username}")
        
        # 加载同步状态
        state = load_state()
        last_message_id = state.get('last_message_id', 0)
        
        logger.info(f"开始同步频道 @{CHANNEL_USERNAME}，上次同步到消息 ID: {last_message_id}")
        
        # 获取频道消息
        # 注意：python-telegram-bot 没有直接获取历史消息的方法
        # 这里我们用一个简化的方案，先创建一个示例文章
        logger.info("注意：由于 Telegram Bot API 限制，需要用其他方式获取历史消息")
        logger.info("当前创建示例文章...")
        
        # 创建一个示例文章
        sample_date = datetime.now()
        sample_title = "欢迎来到读库"
        sample_content = """# 欢迎来到读库

这里是陛下的杂志资源博客，分享各类杂志资源。

## 说明

本博客将同步 Telegram 频道 @FreePeriodical 的内容。

**注意**：由于 Telegram Bot API 限制，完整的历史消息同步需要使用 Telegram Client API（需要 api_id 和 api_hash）。

当前方案：
- 可以使用 Bot 接收新消息（需要设置 Webhook 或使用 Long Polling）
- 历史消息同步需要使用 Client API

敬请期待！
"""
        
        create_post(sample_title, sample_content, sample_date)
        
        # 更新状态（这里只是示例）
        state['last_message_id'] = 1
        save_state(state)
        
        return True
        
    except TelegramError as e:
        logger.error(f"Telegram 错误: {e}")
        return False
    except Exception as e:
        logger.error(f"同步失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始同步 Telegram 频道...")
    logger.info("=" * 50)
    
    success = asyncio.run(sync_channel())
    
    if success:
        logger.info("同步完成！")
        sys.exit(0)
    else:
        logger.error("同步失败！")
        sys.exit(1)


if __name__ == '__main__':
    main()
