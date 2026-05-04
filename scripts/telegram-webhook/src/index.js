/**
 * Telegram → GitHub Blog Sync Webhook Worker
 * 
 * 接收 Telegram Bot 的 webhook 推送，处理新消息并同步到博客
 * 
 * 环境变量（通过 `wrangler secret put` 设置）：
 *   TELEGRAM_BOT_TOKEN: Bot API Token
 *   GITHUB_TOKEN: GitHub Personal Access Token (with repo scope)
 */

const TELEGRAM_API = 'https://api.telegram.org';
const GITHUB_API = 'https://api.github.com';

// 可靠地将 Uint8Array 转为 base64（适用于任意字节值，包括 >= 0x80）
function uint8ToBase64(uint8) {
  let binary = '';
  for (let i = 0; i < uint8.length; i++) {
    binary += String.fromCharCode(uint8[i]);
  }
  return btoa(binary);
}

// 将任意 Unicode 字符串可靠地转为 base64（Cloudflare Workers 专用）
async function stringToBase64(str) {
  const encoder = new TextEncoder();
  const uint8 = encoder.encode(str);
  return uint8ToBase64(uint8);
}

async function uploadGitHubFile(token, repo, path, content, message) {
  const url = `${GITHUB_API}/repos/${repo}/contents/${path}`;
  
  let sha = null;
  try {
    const getResp = await fetch(url, {
      headers: { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'telegram-blog-sync-worker/1.0' }
    });
    if (getResp.ok) {
      const data = await getResp.json();
      sha = data.sha;
    }
  } catch (e) {}

  const body = {
    message,
    content,
    ...(sha ? { sha } : {})
  };

  const resp = await fetch(url, {
    method: 'PUT',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'telegram-blog-sync-worker/1.0'
    },
    body: JSON.stringify(body)
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`GitHub API error: ${resp.status} ${err}`);
  }

  return resp.json();
}

export default {
  async fetch(request, env, ctx) {
    // 健康检查端点
    if (request.method === 'GET') {
      return new Response(JSON.stringify({
        status: 'ok',
        worker: 'telegram-blog-sync',
        hasBotToken: !!env.TELEGRAM_BOT_TOKEN,
        hasGitHubToken: !!env.GITHUB_TOKEN
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    try {
      const update = await request.json();
      
      // 忽略非消息类更新
      if (!update.message && !update.channel_post) {
        return new Response('OK', { status: 200 });
      }

      const msg = update.message || update.channel_post;
      const msgId = msg.message_id;
      const text = msg.caption || msg.text || '';
      const photo = msg.photo;

      // 跳过带按钮的消息（广告、投票等）
      if (msg.reply_markup?.inline_keyboard?.length > 0) {
        return new Response('OK (has buttons, skipped)', { status: 200 });
      }

      // 跳过纯文字消息（只发文字不带图片的不算正式帖子）
      if (text && !photo) {
        return new Response('OK (text-only, skipped)', { status: 200 });
      }

      // 跳过空消息
      if (!text && !photo) {
        return new Response('OK', { status: 200 });
      }

      // 检查必要配置
      if (!env.TELEGRAM_BOT_TOKEN || !env.GITHUB_TOKEN) {
        return new Response(JSON.stringify({ error: 'Missing TELEGRAM_BOT_TOKEN or GITHUB_TOKEN' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      // 提取标题（第一行，最多60字符）
      const title = text.split('\n')[0].slice(0, 60) || `Post ${msgId}`;
      const date = new Date(msg.date * 1000).toISOString();
      const safeTitle = title.replace(/\"/g, '\\"');
      // 从正文（标题之后）提取 description，至少需要 20 字符才算有效摘要，否则留空让主题使用 og description
      const rawDesc = text.split('\n').slice(1).join(' ').replace(/\"/g, '\\"');
      const desc = rawDesc.slice(0, 150).length >= 20 ? rawDesc.slice(0, 150) : '';
      const channelUsername = msg.chat?.username || 'QiKan2026';
      const telegramLink = `https://t.me/${channelUsername}/${msgId}`;

      let imageRelPath = '';
      let imageContent = null;

      // 下载图片（如果有）
      if (photo && photo.length > 0) {
        const bestPhoto = photo[photo.length - 1];
        const fileResp = await fetch(
          `${TELEGRAM_API}/bot${env.TELEGRAM_BOT_TOKEN}/getFile?file_id=${bestPhoto.file_id}`
        );
        const fileData = await fileResp.json();
        
        if (fileData.ok && fileData.result) {
          const filePath = fileData.result.file_path;
          const fileUrl = `${TELEGRAM_API}/file/bot${env.TELEGRAM_BOT_TOKEN}/${filePath}`;
          
          const imgResp = await fetch(fileUrl);
          if (imgResp.ok) {
            imageContent = await imgResp.arrayBuffer();
            imageRelPath = `/assets/blog/${msgId}.jpg`;
          }
        }
      }

      // 解析 message entities，提取 hashtag 作为标签
      const hashtagSet = new Set();
      if (msg.entities && Array.isArray(msg.entities)) {
        for (const entity of msg.entities) {
          if (entity.type === 'hashtag') {
            const hashtagText = text.slice(entity.offset, entity.offset + entity.length);
            // 去掉 # 符号，保留标签内容
            const tag = hashtagText.replace(/^#/, '').trim();
            if (tag) hashtagSet.add(tag);
          }
        }
      }
      // 如果 entity 解析不到，备用：直接从文本中正则匹配
      if (hashtagSet.size === 0) {
        const hashtagRegex = /#[^\s#]+/g;
        let match;
        while ((match = hashtagRegex.exec(text)) !== null) {
          const tag = match[0].replace(/^#/, '').trim();
          if (tag) hashtagSet.add(tag);
        }
      }
      const tagsLine = hashtagSet.size > 0
        ? `tags: [${Array.from(hashtagSet).map(t => `"${t}"`).join(', ')}]`
        : 'tags: ["自动同步"]';

      // 构建 markdown 内容
      const heroImage = imageRelPath ? `heroImage: "${imageRelPath}"` : 'heroImage: ""';
      const markdownContent = `---
title: "${safeTitle}"
pubDatetime: ${date}
description: "${desc}"
${heroImage}
${tagsLine}
---

${text}

---
📌 [查看 Telegram 频道原文](${telegramLink})
`;

      const blogDir = env.BLOG_POSTS_DIR || 'src/content/blog';
      const imageDir = env.IMAGE_ASSETS_DIR || 'public/assets/blog';
      const repo = env.GITHUB_REPO || 'lionel518/imperial-blog';

      // 1. 上传图片（如果存在）
      if (imageContent) {
        const imgPath = `${imageDir}/${msgId}.jpg`;
        const uint8 = new Uint8Array(imageContent);
        await uploadGitHubFile(
          env.GITHUB_TOKEN,
          repo,
          imgPath,
          uint8ToBase64(uint8),
          `Add image for post ${msgId}`
        );
      }

      // 2. 上传 markdown 文件
      await uploadGitHubFile(
        env.GITHUB_TOKEN,
        repo,
        `${blogDir}/${msgId}.md`,
        await stringToBase64(markdownContent),
        `Sync post ${msgId}: ${title.slice(0, 30)}`
      );

      console.log(`Synced post ${msgId}: ${title}`);

      return new Response('OK', { status: 200 });
    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};
