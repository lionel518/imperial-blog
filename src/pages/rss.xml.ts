import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import { getPath } from "@/utils/getPath";
import getSortedPosts from "@/utils/getSortedPosts";
import { SITE } from "@/config";

export async function GET() {
  const posts = await getCollection("blog");
  const sortedPosts = getSortedPosts(posts);
  const customData = `
    <language>zh-cn</language>
    <managingEditor>hi@themagazine.top (读库)</managingEditor>
    <webMaster>hi@themagazine.top (读库)</webMaster>
    <copyright>Copyright ${new Date().getFullYear()} 读库</copyright>
    <ttl>60</ttl>
  `.trim();

  return rss({
    title: SITE.title,
    description: SITE.desc,
    site: SITE.website,
    items: sortedPosts.map(({ data, id, filePath }) => ({
      link: getPath(id, filePath),
      title: data.title,
      description: data.description,
      pubDate: new Date(data.modDatetime ?? data.pubDatetime),
    })),
    customData,
  });
}
