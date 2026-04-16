export const SITE = {
  website: "https://themagazine.top/", // replace this with your deployed domain
  author: "读库",
  profile: "https://themagazine.top/",
  desc: "分享知识与思考",
  title: "读库",
  ogImage: "astropaper-og.jpg",
  lightAndDarkMode: true,
  postPerIndex: 4,
  postPerPage: 4,
  scheduledPostMargin: 15 * 60 * 1000, // 15 minutes
  showArchives: false,
  showBackButton: true, // show back button in post detail
  editPost: {
    enabled: false,
    text: "编辑页面",
    url: "https://github.com/satnaing/astro-paper/edit/main/",
  },
  dynamicLgImage: true,
  dir: "ltr", // "rtl" | "auto"
  lang: "zh-CN", // html lang code. Set this empty and default will be "en"
  timezone: "Asia/Shanghai", // Default global timezone (IANA format) https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
} as const;
