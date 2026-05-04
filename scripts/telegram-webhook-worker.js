/**
 * Telegram → GitHub Blog Sync Webhook Worker
 * 
 * 接收 Telegram Bot 的 webhook 推送，处理新消息并同步到博客
 * 
 * 环境变量（需在 Cloudflare Worker 设置）：
 *   TELEGRAM_BOT_TOKEN: Bot API Token
 *   GITHUB_TOKEN: GitHub Personal Access Token (with repo scope)
 *   GITHUB_REPO: "lionel518/imperial-blog"
 *   BLOG_POSTS_DIR: "src/content/blog" (默认)
 *   IMAGE_ASSETS_DIR: "public/assets/blog" (默认)
 */

const TELEGRAM_API = 'https://api.telegram.org';
const GITHUB_API = 'https://api.github.com';

export default {
  async fetch(request, env, ctx) {
    // 只接受 POST 请求
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
      const chatId = msg.chat?.id;
      const msgId = msg.message_id;
      const text = msg.caption || msg.text || '';
      const photo = msg.photo;

      // 跳过空消息
      if (!text && !photo) {
        return new Response('OK', { status: 200 });
      }

      // 提取标题（第一行，最多60字符）
      const title = text.split('\n')[0].slice(0, 60) || `Post ${msgId}`;
      
      // 生成 frontmatter
      const date = new Date(msg.date * 1000).toISOString();
      const safeTitle = title.replace(/"/g, '\\"');
      const desc = text.split('\n').slice(1).join(' ').slice(0, 150).replace(/"/g, '\\"') || title;
      const channelUsername = msg.chat?.username || 'QiKan2026';
      const telegramLink = `https://t.me/${channelUsername}/${msgId}`;

      let imageRelPath = '';
      let imageContent = null;

      // 下载图片（如果有）
      if (photo && photo.length > 0) {
        const bestPhoto = photo[photo.length - 1]; // 最大尺寸
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

      // 构建 markdown 内容
      const heroImage = imageRelPath ? `heroImage: "${imageRelPath}"` : 'heroImage: ""';
      const markdownContent = `---
title: "${safeTitle}"
pubDatetime: ${date}
description: "${desc}"
${heroImage}
tags: ["自动同步"]
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
        await uploadGitHubFile(
          env.GITHUB_TOKEN,
          repo,
          imgPath,
          btoa(String.fromCharCode(...new Uint8Array(imageContent))),
          `Add image for post ${msgId}`
        );
      }

      // 2. 上传 markdown 文件
      await uploadGitHubFile(
        env.GITHUB_TOKEN,
        repo,
        `${blogDir}/${msgId}.md`,
        btoa(unescape(encodeURIComponent(markdownContent))),
        `Sync post ${msgId}: ${title.slice(0, 30)}`
      );

      console.log(`✅ Synced post ${msgId}: ${title}`);

      return new Response('OK', { status: 200 });
    } catch (error) {
      console.error('❌ Error:', error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

async function uploadGitHubFile(token, repo, path, content, message) {
  const url = `${GITHUB_API}/repos/${repo}/contents/${path}`;
  
  // 先尝试获取当前文件 SHA（如果存在）
  let sha = null;
  try {
    const getResp = await fetch(url, {
      headers: { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json' }
    });
    if (getResp.ok) {
      const data = await getResp.json();
      sha = data.sha;
    }
  } catch (e) {
    // 文件不存在，正常
  }

  // 上传文件
  const body = {
    message,
    content,
    ...(sha ? { sha } : {}) // 更新文件时需要 sha
  };

  const resp = await fetch(url, {
    method: 'PUT',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`GitHub API error: ${resp.status} ${err}`);
  }

  return resp.json();
}
