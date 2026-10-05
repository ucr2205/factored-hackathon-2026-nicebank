// Prints docs/pitch/deck/deck.html (6 slides, 1920x1080) to PDF with local Chrome, plus one PNG per slide for review.
// Usage (from video/): node tools/deck-pdf.mjs [output.pdf]
import { chromium } from "playwright";

const deck = new URL("../../docs/pitch/deck/", import.meta.url);
const fsPath = (u) => u.pathname.replace(/^\/([A-Za-z]:)/, "$1");
const out = process.argv[2] ?? fsPath(new URL("NiceBank-pitch.pdf", deck));

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(new URL("deck.html", deck).href);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);
const slides = await page.locator("section.slide").count();
for (let i = 0; i < slides; i++) {
  await page.locator("section.slide").nth(i).screenshot({ path: fsPath(new URL(`preview-${i + 1}.png`, deck)) });
}
await page.pdf({ path: out, width: "1920px", height: "1080px", printBackground: true, preferCSSPageSize: true });
await browser.close();
console.log(`wrote ${out} (${slides} slides)`);
