# AI Visual Studio — Instagram public post extractor

This is a small backend adapter around the open-source `parth-dl` extraction engine. It is intended for low-volume personal use on public Instagram posts/reels, including image carousels where Instagram exposes the media to logged-out clients.

## Deploy (free-tier hosting may sleep)

1. Create a GitHub repository and upload the contents of this folder (not the enclosing folder).
2. In Render, choose **New → Blueprint** and connect that repository. Render reads `render.yaml` and installs the requirements.
3. After deployment, open `https://YOUR-SERVICE.onrender.com/health`. It should return JSON with `"ok": true`.
4. Copy the service origin only, e.g. `https://ai-visual-instagram-extractor.onrender.com`. Enter it in the Instagram extractor endpoint setting inside AI Visual Studio.

## API

`POST /extract`

```json
{"url":"https://www.instagram.com/p/SHORTCODE/"}
```

Returns `data.images` as direct image CDN URLs and `data.imageDetails` with the media index, reported width/height and URL. Browser image loading can independently confirm the actual dimensions of the file delivered. CDN URLs are signed and may expire; re-extract rather than storing old URLs.

## Limits

- Supports only public `/p/`, `/reel/`, `/tv/` links exposed to logged-out clients.
- No login, cookies, private content, stories, highlights, or bypassing access controls.
- Instagram may throttle or change response formats; this is not guaranteed for every public-looking post.
- Keep the service private to low-volume personal use. It includes a simple per-IP rate limit; a free service may sleep after inactivity.
- This adapter does not persist or proxy image files. The browser opens the actual CDN URL so you can long-press/save in Safari.
- Follow Instagram's terms and applicable law; only save content you have permission to use.

## Health check

`GET /health`
