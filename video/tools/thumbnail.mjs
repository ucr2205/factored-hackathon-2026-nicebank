// Renders thumbnail/thumbnail.html to thumbnail/nicebank-thumbnail.png (1280x720, YouTube size) with local Chrome.
// Usage: node tools/thumbnail.mjs
import { chromium } from "playwright";

const dir = new URL("../thumbnail/", import.meta.url);
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
await page.goto(new URL("thumbnail.html", dir).href);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
await page.screenshot({ path: new URL("nicebank-thumbnail.png", dir).pathname.replace(/^\/([A-Za-z]:)/, "$1") });
await browser.close();
console.log("wrote thumbnail/nicebank-thumbnail.png");
