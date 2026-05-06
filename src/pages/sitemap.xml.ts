import { getCollection } from "astro:content";
import type { CollectionEntry } from "astro:content";
import { SITE } from "@/config";
import { getPath } from "@/utils/getPath";
import getUniqueTags from "@/utils/getUniqueTags";
import getSortedPosts from "@/utils/getSortedPosts";

interface SitemapUrl {
  url: string;
  lastmod: string;
  changefreq?: string;
  priority?: number;
}

function xmlEscape(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET(): Promise<Response> {
  const posts = await getCollection("blog", ({ data }) => !data.draft);

  const siteUrl = SITE.website.replace(/\/$/, "");

  const postUrls: SitemapUrl[] = posts.map(post => ({
    url: `${siteUrl}${getPath(post.id, post.filePath)}/`,
    lastmod: new Date(post.data.modDatetime ?? post.data.pubDatetime).toISOString().split("T")[0],
    changefreq: "weekly",
    priority: 0.8,
  }));

  // Tag pages
  const tagSet = getUniqueTags(posts);
  const tagUrls: SitemapUrl[] = tagSet.map(({ tag }) => ({
    url: `${siteUrl}/tags/${tag}/`,
    lastmod: new Date().toISOString().split("T")[0],
    changefreq: "weekly",
    priority: 0.5,
  }));

  // Pagination pages
  const sortedPosts = getSortedPosts(posts);
  const postsPerPage = SITE.postPerPage || 4;
  const totalPages = Math.ceil(sortedPosts.length / postsPerPage);
  const pageUrls: SitemapUrl[] = Array.from({ length: totalPages }, (_, i) => ({
    url: `${siteUrl}/posts/${i > 0 ? `${i + 1}/` : ""}`,
    lastmod: new Date().toISOString().split("T")[0],
    changefreq: "daily",
    priority: i === 0 ? 1.0 : 0.6,
  }));

  const allUrls = [
    { url: siteUrl + "/", lastmod: new Date().toISOString().split("T")[0], changefreq: "daily", priority: 1.0 },
    { url: `${siteUrl}/tags/`, lastmod: new Date().toISOString().split("T")[0], changefreq: "weekly", priority: 0.5 },
    { url: `${siteUrl}/about/`, lastmod: new Date().toISOString().split("T")[0], changefreq: "monthly", priority: 0.4 },
    { url: `${siteUrl}/search/`, lastmod: new Date().toISOString().split("T")[0], changefreq: "monthly", priority: 0.3 },
    ...pageUrls,
    ...tagUrls,
    ...postUrls,
  ];

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
${allUrls
  .map(
    entry => `  <url>
    <loc>${xmlEscape(entry.url)}</loc>
    <lastmod>${entry.lastmod}</lastmod>${entry.changefreq ? `\n    <changefreq>${entry.changefreq}</changefreq>` : ""}${entry.priority !== undefined ? `\n    <priority>${entry.priority.toFixed(1)}</priority>` : ""}
  </url>`
  )
  .join("\n")}
</urlset>`;

  return new Response(sitemap, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
