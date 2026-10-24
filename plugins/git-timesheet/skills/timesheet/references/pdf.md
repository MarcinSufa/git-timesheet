# PDF output

`render.py --format pdf` prints the filled template with headless Chromium
(A4 landscape from the template's `@page` rule, backgrounds on). Engines, in
order (`--pdf-engine auto|playwright|chrome`):

1. **Python Playwright** — used when `import playwright` works and its
   Chromium is installed.
2. **Chrome / Chromium binary** — `$GIT_TIMESHEET_CHROME`, then `chromium`,
   `chromium-browser`, `google-chrome(-stable)`, `chrome` or `microsoft-edge`
   on `PATH`, the macOS app bundles, or the newest build in the Playwright cache
   (`~/.cache/ms-playwright`, `~/Library/Caches/ms-playwright`,
   `$PLAYWRIGHT_BROWSERS_PATH`). Runs with `--headless --print-to-pdf` and a
   throw-away profile directory.

If neither works, `render.py` exits with code 3, keeps the HTML next to where
the PDF would be, still writes any CSV, and prints what to install:

```bash
npx -y playwright install chromium-headless-shell          # ~100 MB, no sudo
python3 -m pip install --user playwright && python3 -m playwright install chromium
sudo npx -y playwright install-deps chromium               # Linux: missing shared libraries
```

Show the user these options; do not install anything without asking. If the
PDF still cannot be produced, deliver the CSV/HTML and say so plainly.

Chromium is started with `--no-sandbox`, as Playwright does by default; the
input is the local HTML that `render.py` just wrote. On Ubuntu 24.04 the
Chromium sandbox is otherwise blocked by AppArmor.

## Optional: Playwright MCP

When the scripts cannot print but a Playwright MCP server is connected, it can
convert the kept HTML. Plugin installs expose the tools as
`mcp__plugin_playwright_playwright__browser_*`, standalone servers as
`mcp__playwright__browser_*`. Check for **both** names; use whichever exists.
If neither exists, skip this path.

1. Serve the folder with the HTML (the MCP browser may not read `file://`):
   `python3 -m http.server 8772 --bind 127.0.0.1 --directory "<out dir>"`
   (run in the background; on Windows use `py -m http.server ...`).
2. One `browser_run_code` call for all files:

   ```javascript
   async (page) => {
     for (const name of ["Timesheet_Jane_Doe_Weekly_20260401_20260405"]) {
       await page.goto(`http://127.0.0.1:8772/${name}.html`);
       await page.pdf({ path: `<out dir>/${name}.pdf`, format: "A4", landscape: true,
                        printBackground: true,
                        margin: { top: "20mm", bottom: "20mm", left: "20mm", right: "20mm" } });
     }
   }
   ```
3. Stop the HTTP server, delete the HTML files and any `.playwright-mcp/`
   snapshot files.

The MCP is also handy for template previews (`browser_navigate` +
`browser_take_screenshot`).
