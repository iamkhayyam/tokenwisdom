// Email via Resend. Falls back to console logging in dev (no RESEND_API_KEY),
// so the full auth flow is testable locally without sending real mail.
let resend = null;
const FROM = process.env.MAIL_FROM || "Token Wisdom <community@tokenwisdom.ai>";

function client() {
  if (resend) return resend;
  if (!process.env.RESEND_API_KEY) return null;
  const { Resend } = require("resend");
  resend = new Resend(process.env.RESEND_API_KEY);
  return resend;
}

async function send({ to, subject, html, text }) {
  const c = client();
  if (!c) {
    console.log(`\n[email:dev] to=${to}\n  subject: ${subject}\n  ${text || html}\n`);
    return { dev: true };
  }
  const { data, error } = await c.emails.send({ from: FROM, to, subject, html, text });
  if (error) throw new Error(`Resend: ${error.message || JSON.stringify(error)}`);
  return data;
}

const wrap = (title, bodyHtml) => `
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:480px;margin:0 auto;color:#2b2722">
  <p style="font:600 12px/1 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#b4521f">Token Wisdom</p>
  <h1 style="font-size:20px;margin:.4em 0 .6em">${title}</h1>
  ${bodyHtml}
  <p style="font-size:12px;color:#8a8278;margin-top:2em">If you didn't request this, you can ignore this email.</p>
</div>`;

async function sendMagicLink({ to, url }) {
  return send({
    to,
    subject: "Your Token Wisdom sign-in link",
    text: `Sign in to Token Wisdom: ${url}\n\nThis link expires shortly and can be used once.`,
    html: wrap(
      "Sign in to comment",
      `<p>Click to sign in and join the conversation. This link expires shortly and works once.</p>
       <p><a href="${url}" style="display:inline-block;background:#b4521f;color:#fff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:600">Sign in</a></p>
       <p style="font-size:12px;color:#8a8278">Or paste this URL: ${url}</p>`
    ),
  });
}

async function sendModerationNotice({ to, postSlug, body, approveUrl, hideUrl }) {
  return send({
    to,
    subject: `New response pending — ${postSlug}`,
    text: `A new response is awaiting approval on ${postSlug}:\n\n"${body}"\n\nApprove: ${approveUrl}\nHide: ${hideUrl}`,
    html: wrap(
      "A response is awaiting approval",
      `<p style="font:12px ui-monospace,monospace;color:#8a8278">${postSlug}</p>
       <blockquote style="border-left:3px solid #e2ddd4;margin:.6em 0;padding:.2em 0 .2em 1em;color:#4a453d">${body}</blockquote>
       <p>
         <a href="${approveUrl}" style="display:inline-block;background:#2b7a4b;color:#fff;text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600;margin-right:8px">Approve</a>
         <a href="${hideUrl}" style="display:inline-block;background:#9a3434;color:#fff;text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600">Hide</a>
       </p>`
    ),
  });
}

module.exports = { send, sendMagicLink, sendModerationNotice };
