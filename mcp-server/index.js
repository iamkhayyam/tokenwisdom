#!/usr/bin/env node

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod/v4");

// ─── Ghost Content API helpers ───────────────────────────────────────────────

async function ghostFetch(ghostUrl, apiKey, endpoint, params = {}) {
  const base = ghostUrl.replace(/\/+$/, "");
  const url = new URL(`${base}/ghost/api/content/${endpoint}/`);
  url.searchParams.set("key", apiKey);
  for (const [k, v] of Object.entries(params)) {
    url.searchParams.set(k, String(v));
  }
  const res = await fetch(url.toString(), {
    headers: { "Accept-Version": "v5.0" },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ghost API ${res.status}: ${body}`);
  }
  return res.json();
}

/**
 * Paginate through all records for a Ghost Content API endpoint.
 * Ghost 6+ caps limit at 100, so we page through with limit=100.
 */
async function ghostFetchAll(ghostUrl, apiKey, endpoint, extraParams = {}) {
  const all = [];
  let page = 1;
  while (true) {
    const data = await ghostFetch(ghostUrl, apiKey, endpoint, {
      ...extraParams,
      limit: 100,
      page,
    });
    const key = Object.keys(data).find((k) => k !== "meta");
    if (!key || !data[key]) break;
    all.push(...data[key]);
    const pagination = data.meta?.pagination;
    if (!pagination || page >= pagination.pages) break;
    page++;
  }
  return all;
}

// ─── GitHub API helpers ──────────────────────────────────────────────────────

const GITHUB_API = "https://api.github.com";

async function githubRequest(method, path, token, body = null) {
  const opts = {
    method,
    headers: {
      Authorization: `token ${token}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "ghost-github-backup-mcp",
    },
  };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${GITHUB_API}${path}`, opts);
  if (res.status === 404) return null;
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub ${res.status}: ${text}`);
  }
  if (res.status === 204) return {};
  return res.json();
}

/** Create or update a file in a GitHub repo. */
async function upsertFile(owner, repo, filePath, content, token, message) {
  const path = `/repos/${owner}/${repo}/contents/${filePath}`;
  // Check if file already exists to get its SHA
  const existing = await githubRequest("GET", path, token);
  const body = {
    message,
    content: Buffer.from(content).toString("base64"),
  };
  if (existing?.sha) body.sha = existing.sha;
  return githubRequest("PUT", path, token, body);
}

// ─── Build backup payload ────────────────────────────────────────────────────

async function buildBackup(ghostUrl, apiKey) {
  const log = [];
  log.push("Fetching posts...");
  const posts = await ghostFetchAll(ghostUrl, apiKey, "posts", {
    include: "tags,authors",
    formats: "html,mobiledoc",
  });
  log.push(`  → ${posts.length} posts`);

  log.push("Fetching pages...");
  const pages = await ghostFetchAll(ghostUrl, apiKey, "pages", {
    include: "tags,authors",
    formats: "html,mobiledoc",
  });
  log.push(`  → ${pages.length} pages`);

  log.push("Fetching tags...");
  const tags = await ghostFetchAll(ghostUrl, apiKey, "tags", {
    include: "count.posts",
  });
  log.push(`  → ${tags.length} tags`);

  log.push("Fetching authors...");
  const authors = await ghostFetchAll(ghostUrl, apiKey, "authors", {
    include: "count.posts",
  });
  log.push(`  → ${authors.length} authors`);

  log.push("Fetching settings...");
  const settingsData = await ghostFetch(ghostUrl, apiKey, "settings");
  const settings = settingsData.settings;
  log.push("  → done");

  log.push("Fetching tiers...");
  let tiers = [];
  try {
    tiers = await ghostFetchAll(ghostUrl, apiKey, "tiers");
    log.push(`  → ${tiers.length} tiers`);
  } catch {
    log.push("  → tiers endpoint not available (skipped)");
  }

  return {
    log,
    data: { posts, pages, tags, authors, settings, tiers },
  };
}

// ─── Format helpers ──────────────────────────────────────────────────────────

function slugify(str) {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function postToMarkdown(post) {
  const frontmatter = [
    "---",
    `id: "${post.id}"`,
    `title: "${(post.title || "").replace(/"/g, '\\"')}"`,
    `slug: "${post.slug}"`,
    `published_at: "${post.published_at || ""}"`,
    `updated_at: "${post.updated_at || ""}"`,
    `status: "${post.status || "published"}"`,
    `featured: ${post.featured || false}`,
    `feature_image: "${post.feature_image || ""}"`,
    `tags: [${(post.tags || []).map((t) => `"${t.name}"`).join(", ")}]`,
    `authors: [${(post.authors || []).map((a) => `"${a.name}"`).join(", ")}]`,
    `excerpt: "${(post.excerpt || "").replace(/"/g, '\\"').replace(/\n/g, " ").slice(0, 200)}"`,
    "---",
    "",
  ].join("\n");
  // Use plaintext or strip HTML for the body
  const body = post.html || post.plaintext || "";
  return frontmatter + body;
}

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "ghost-github-backup",
  version: "1.0.0",
  description:
    "Back up a Ghost CMS site (posts, pages, tags, authors, settings) to a GitHub repository.",
});

// ── Tool 1: Preview / Audit ──────────────────────────────────────────────────
server.tool(
  "ghost_preview",
  "Fetch and summarise what would be backed up from a Ghost site (posts, pages, tags, authors, settings). Useful for a dry-run before pushing to GitHub.",
  {
    ghost_url: z.string().describe("Ghost site URL, e.g. https://yoursite.ghost.io"),
    ghost_api_key: z.string().describe("Ghost Content API key"),
  },
  async ({ ghost_url, ghost_api_key }) => {
    try {
      const { log, data } = await buildBackup(ghost_url, ghost_api_key);
      const summary = [
        ...log,
        "",
        "=== Backup Summary ===",
        `Posts:    ${data.posts.length}`,
        `Pages:    ${data.pages.length}`,
        `Tags:     ${data.tags.length}`,
        `Authors:  ${data.authors.length}`,
        `Tiers:    ${data.tiers.length}`,
        `Settings: ${Object.keys(data.settings || {}).length} keys`,
        "",
        "Recent posts:",
        ...data.posts.slice(0, 10).map(
          (p) => `  • ${p.title}  (${p.slug})  [${p.published_at?.slice(0, 10) || "draft"}]`
        ),
      ];
      return { content: [{ type: "text", text: summary.join("\n") }] };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ── Tool 2: Full Backup to GitHub ────────────────────────────────────────────
server.tool(
  "ghost_backup_to_github",
  "Back up an entire Ghost site (posts as Markdown, pages, tags, authors, settings, full JSON dump) to a GitHub repository. Creates a structured directory tree and commits all files.",
  {
    ghost_url: z.string().describe("Ghost site URL, e.g. https://yoursite.ghost.io"),
    ghost_api_key: z.string().describe("Ghost Content API key"),
    github_token: z.string().describe("GitHub personal access token with repo scope"),
    github_owner: z.string().describe("GitHub repository owner (user or org)"),
    github_repo: z.string().describe("GitHub repository name"),
    branch: z.string().optional().describe("Branch to push to (default: main)"),
  },
  async ({ ghost_url, ghost_api_key, github_token, github_owner, github_repo, branch }) => {
    const targetBranch = branch || "main";
    const progress = [];
    try {
      // 1. Fetch everything from Ghost
      const { log, data } = await buildBackup(ghost_url, ghost_api_key);
      progress.push(...log);

      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const commitMsg = `Ghost backup ${timestamp}`;

      // 2. Push full JSON dump
      progress.push("\nPushing full JSON backup...");
      await upsertFile(
        github_owner,
        github_repo,
        "backup/ghost-backup.json",
        JSON.stringify(data, null, 2),
        github_token,
        commitMsg
      );
      progress.push("  → backup/ghost-backup.json ✓");

      // 3. Push individual posts as Markdown
      progress.push(`\nPushing ${data.posts.length} posts as Markdown...`);
      let postCount = 0;
      for (const post of data.posts) {
        const filename = `${post.slug || slugify(post.title || post.id)}.md`;
        const md = postToMarkdown(post);
        await upsertFile(
          github_owner,
          github_repo,
          `backup/posts/${filename}`,
          md,
          github_token,
          `Backup post: ${post.title || post.slug}`
        );
        postCount++;
        if (postCount % 25 === 0) {
          progress.push(`  → ${postCount}/${data.posts.length} posts pushed...`);
        }
      }
      progress.push(`  → ${postCount} posts ✓`);

      // 4. Push individual pages as Markdown
      if (data.pages.length > 0) {
        progress.push(`\nPushing ${data.pages.length} pages as Markdown...`);
        for (const page of data.pages) {
          const filename = `${page.slug || slugify(page.title || page.id)}.md`;
          const md = postToMarkdown(page);
          await upsertFile(
            github_owner,
            github_repo,
            `backup/pages/${filename}`,
            md,
            github_token,
            `Backup page: ${page.title || page.slug}`
          );
        }
        progress.push(`  → ${data.pages.length} pages ✓`);
      }

      // 5. Push tags
      progress.push("\nPushing tags...");
      await upsertFile(
        github_owner,
        github_repo,
        "backup/tags.json",
        JSON.stringify(data.tags, null, 2),
        github_token,
        commitMsg
      );
      progress.push("  → backup/tags.json ✓");

      // 6. Push authors
      progress.push("Pushing authors...");
      await upsertFile(
        github_owner,
        github_repo,
        "backup/authors.json",
        JSON.stringify(data.authors, null, 2),
        github_token,
        commitMsg
      );
      progress.push("  → backup/authors.json ✓");

      // 7. Push settings
      progress.push("Pushing settings...");
      await upsertFile(
        github_owner,
        github_repo,
        "backup/settings.json",
        JSON.stringify(data.settings, null, 2),
        github_token,
        commitMsg
      );
      progress.push("  → backup/settings.json ✓");

      // 8. Push tiers if present
      if (data.tiers.length > 0) {
        progress.push("Pushing tiers...");
        await upsertFile(
          github_owner,
          github_repo,
          "backup/tiers.json",
          JSON.stringify(data.tiers, null, 2),
          github_token,
          commitMsg
        );
        progress.push("  → backup/tiers.json ✓");
      }

      // 9. Push a manifest / README
      const readme = [
        `# Token Wisdom – Ghost Backup`,
        "",
        `**Backed up:** ${timestamp}`,
        `**Source:** ${ghost_url}`,
        "",
        `| Content    | Count |`,
        `|------------|-------|`,
        `| Posts      | ${data.posts.length} |`,
        `| Pages      | ${data.pages.length} |`,
        `| Tags       | ${data.tags.length} |`,
        `| Authors    | ${data.authors.length} |`,
        `| Tiers      | ${data.tiers.length} |`,
        "",
        "## Directory Structure",
        "```",
        "backup/",
        "├── ghost-backup.json    # Full JSON dump of everything",
        "├── posts/               # Each post as Markdown with YAML frontmatter",
        "├── pages/               # Each page as Markdown with YAML frontmatter",
        "├── tags.json",
        "├── authors.json",
        "├── settings.json",
        "└── tiers.json",
        "```",
      ].join("\n");

      await upsertFile(
        github_owner,
        github_repo,
        "backup/README.md",
        readme,
        github_token,
        commitMsg
      );
      progress.push("\n  → backup/README.md ✓");

      progress.push(
        `\n✅ Backup complete! ${data.posts.length} posts, ${data.pages.length} pages, ${data.tags.length} tags pushed to ${github_owner}/${github_repo}`
      );
      progress.push(
        `   View at: https://github.com/${github_owner}/${github_repo}/tree/${targetBranch}/backup`
      );

      return { content: [{ type: "text", text: progress.join("\n") }] };
    } catch (err) {
      progress.push(`\n❌ Error: ${err.message}`);
      return {
        content: [{ type: "text", text: progress.join("\n") }],
        isError: true,
      };
    }
  }
);

// ── Tool 3: Backup single post ───────────────────────────────────────────────
server.tool(
  "ghost_backup_post",
  "Back up a single Ghost post (by slug) to a GitHub repository as Markdown.",
  {
    ghost_url: z.string().describe("Ghost site URL"),
    ghost_api_key: z.string().describe("Ghost Content API key"),
    github_token: z.string().describe("GitHub personal access token"),
    github_owner: z.string().describe("GitHub repo owner"),
    github_repo: z.string().describe("GitHub repo name"),
    post_slug: z.string().describe("Slug of the post to back up"),
  },
  async ({ ghost_url, ghost_api_key, github_token, github_owner, github_repo, post_slug }) => {
    try {
      const data = await ghostFetch(ghost_url, ghost_api_key, `posts/slug/${post_slug}`, {
        include: "tags,authors",
        formats: "html,mobiledoc",
      });
      const post = data.posts?.[0];
      if (!post) return { content: [{ type: "text", text: `Post "${post_slug}" not found.` }], isError: true };

      const md = postToMarkdown(post);
      await upsertFile(
        github_owner,
        github_repo,
        `backup/posts/${post.slug}.md`,
        md,
        github_token,
        `Backup post: ${post.title}`
      );

      return {
        content: [
          {
            type: "text",
            text: `✅ Backed up "${post.title}" → backup/posts/${post.slug}.md\nhttps://github.com/${github_owner}/${github_repo}/blob/main/backup/posts/${post.slug}.md`,
          },
        ],
      };
    } catch (err) {
      return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
    }
  }
);

// ── Tool 4: List recent Ghost posts ──────────────────────────────────────────
server.tool(
  "ghost_list_posts",
  "List recent posts from a Ghost site with title, slug, date, and tags.",
  {
    ghost_url: z.string().describe("Ghost site URL"),
    ghost_api_key: z.string().describe("Ghost Content API key"),
    limit: z.number().optional().describe("Number of posts to return (default 20, max 100)"),
  },
  async ({ ghost_url, ghost_api_key, limit }) => {
    try {
      const n = Math.min(limit || 20, 100);
      const data = await ghostFetch(ghost_url, ghost_api_key, "posts", {
        include: "tags",
        limit: n,
        fields: "id,title,slug,published_at,updated_at,featured",
      });
      const lines = data.posts.map(
        (p) =>
          `• ${p.title}  |  ${p.slug}  |  ${p.published_at?.slice(0, 10) || "draft"}  |  tags: ${(p.tags || []).map((t) => t.name).join(", ") || "none"}`
      );
      return {
        content: [{ type: "text", text: `${data.posts.length} posts:\n\n${lines.join("\n")}` }],
      };
    } catch (err) {
      return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
    }
  }
);

// ── Start ────────────────────────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ghost-github-backup MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
