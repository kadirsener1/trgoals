import asyncio
import re
import json
from playwright.async_api import async_playwright

BASE_CHANNELS = "https://patronsports2.cfd/channels.php"
BASE_PLAYER = "https://patronizle35.cfd/ch.html?id="


def parse_channels(html):
    # 1) JSON object
    try:
        data = json.loads(html)
        if isinstance(data, dict):
            return data

        if isinstance(data, list):
            merged = {}
            for item in data:
                if isinstance(item, dict):
                    merged.update(item)
            return merged
    except:
        pass

    # 2) regex fallback
    matches = re.findall(r'"(yayin[^"]+)"\s*:\s*"([^"]+)"', html)
    return dict(matches)


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(BASE_CHANNELS)
        html = await page.content()

        channels = parse_channels(html)

        print("Kanal sayısı:", len(channels))

        results = []

        for slug, name in channels.items():
            found = set()

            def handle_response(resp):
                if ".m3u8" in resp.url:
                    found.add(resp.url)

            page.on("response", handle_response)

            await page.goto(BASE_PLAYER + slug)
            await page.wait_for_timeout(6000)

            page.remove_listener("response", handle_response)

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
