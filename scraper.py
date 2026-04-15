import asyncio
import json
from playwright.async_api import async_playwright

BASE_CHANNELS = "https://patronsports2.cfd/channels.php"
BASE_PLAYER = "https://patronizle35.cfd/ch.html?id="


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        channels_data = {}

        # 🔥 XHR yakala
        def handle_response(response):
            try:
                if "channels.php" in response.url:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct or "text" in ct:
                        body = response.text()
                        try:
                            data = json.loads(body)
                            if isinstance(data, dict):
                                channels_data.update(data)
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict):
                                        channels_data.update(item)
                        except:
                            pass
            except:
                pass

        page.on("response", handle_response)

        await page.goto(BASE_CHANNELS, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        print("Kanal sayısı:", len(channels_data))

        results = []

        for slug, name in channels_data.items():
            found = set()

            def on_response(resp):
                if ".m3u8" in resp.url:
                    found.add(resp.url)

            page.on("response", on_response)

            await page.goto(BASE_PLAYER + slug)
            await page.wait_for_timeout(6000)

            page.remove_listener("response", on_response)

            if found:
                for u in found:
                    print("[OK]", name, u)
                    results.append((name, u))
            else:
                print("[X]", name)

        await browser.close()

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for name, url in results:
                f.write(f"#EXTINF:-1,{name}\n{url}\n")


if __name__ == "__main__":
    asyncio.run(run())
