export const SITE = {
  website: "https://themagazine.top/", // replace this with your deployed domain
  author: "读库",
  profile: "https://themagazine.top/",
  desc: "读库数字档案馆 — 个人学习资料存档，收录财经、国际刊物、人文生活等优质期刊文摘，供学习研究之用",
  title: "读库 - 个人学习数字档案馆",
  ogImage: "astropaper-og.jpg",
  lightAndDarkMode: true,
  postPerIndex: 4,
  postPerPage: 4,
  scheduledPostMargin: 15 * 60 * 1000, // 15 minutes
  showArchives: true,
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
