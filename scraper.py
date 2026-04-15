import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://patronizle35.cfd"

CHANNELS = {
    "yayinss": "S SPORT 1",
    "yayinss2": "S SPORT 2",
    "yayint1": "TIVIBU SPOR 1",
    "yayint2": "TIVIBU SPOR 2",
    "yayint3": "TIVIBU SPOR 3",
    "yayint4": "TIVIBU SPOR 4",
    "yayinsmarts": "SPOR SMART 1",
    "yayinsms2": "SPOR SMART 2",
    "yayintrtspor": "TRT SPOR",
    "yayintrtspor2": "TRT SPOR 2",
    "yayinas": "A SPOR",
    "yayinatv": "ATV HD",
    "yayintv8": "TV8 HD",
    "yayintv85": "TV8,5 HD",
    "yayinnbatv": "NBA TV",
}

output = []

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for slug, name in CHANNELS.items():
            found = set()

            url = f"{BASE_URL}/ch.html?id={slug}"

            print("Açılıyor:", name)

            async def intercept(response):
                try:
                    if ".m3u8" in response.url:
                        found.add(response.url)
                except:
                    pass

            page.on("response", intercept)

            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # 1) iframe kontrol
            frames = page.frames
            for f in frames:
                try:
                    content = await f.content()
                    if ".m3u8" in content:
                        import re
                        urls = re.findall(r"https?://[^\s'\"]+\.m3u8[^\s'\"]*", content)
                        for u in urls:
                            found.add(u)
                except:
                    pass

            page.remove_listener("response", intercept)

            if found:
                for u in found:
                    print("[OK]", name, u)
                    output.append((name, u))
            else:
                print("[!] Bulunamadı:", name)

        await browser.close()

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in output:
            f.write(f"#EXTINF:-1,{name}\n{url}\n")

if __name__ == "__main__":
    asyncio.run(run())
