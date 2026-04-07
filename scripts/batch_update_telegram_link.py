
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
BLOG_POSTS_DIR = BASE_DIR / 'src' / 'content' / 'blog'
CHANNEL_USERNAME = 'FreePeriodical'

def add_telegram_link_to_post(filepath: Path):
    """给单篇文章添加 Telegram 链接"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 从文件名中提取消息 ID（文件名就是 msg_id.md）
    msg_id = filepath.stem
    
    # 检查是否已经有 Telegram 链接了
    if '查看 Telegram 频道原文' in content:
        print(f"⏭️  跳过 {msg_id}.md（已有链接）")
        return False
    
    # 构建 Telegram 链接
    telegram_link = f"https://t.me/{CHANNEL_USERNAME}/{msg_id}"
    link_section = f"\n---\n📌 [查看 Telegram 频道原文]({telegram_link})\n"
    
    # 在文章末尾添加链接（在 Frontmatter 之后，内容之后）
    # 找到 Frontmatter 的结束位置
    frontmatter_end = content.find('---\n\n', 4)  # 跳过开头的 ---
    if frontmatter_end == -1:
        # 没有找到标准的 Frontmatter 结束，直接在末尾添加
        new_content = content + link_section
    else:
        # 在内容末尾添加
        new_content = content.rstrip() + link_section
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ 更新 {msg_id}.md")
    return True

def main():
    print(f"📝 开始批量更新博客文章，添加 Telegram 链接...")
    print(f"📂 目标目录: {BLOG_POSTS_DIR}")
    print(f"🔗 频道: @{CHANNEL_USERNAME}")
    print("-" * 50)
    
    if not BLOG_POSTS_DIR.exists():
        print(f"❌ 目录不存在: {BLOG_POSTS_DIR}")
        return
    
    md_files = list(BLOG_POSTS_DIR.glob('*.md'))
    print(f"📄 找到 {len(md_files)} 篇文章")
    print()
    
    updated_count = 0
    for filepath in sorted(md_files):
        if add_telegram_link_to_post(filepath):
            updated_count += 1
    
    print("-" * 50)
    print(f"🎉 完成！共更新 {updated_count} 篇文章")

if __name__ == '__main__':
    main()

