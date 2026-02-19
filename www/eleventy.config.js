export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/style.css");
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addPassthroughCopy("src/CNAME");
  eleventyConfig.addPassthroughCopy("src/poap2rss.png");
  eleventyConfig.addPassthroughCopy("src/powered-by-poap.png");

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
    },
  };
}
