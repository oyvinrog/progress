from pathlib import Path


def test_readme_uses_absolute_image_urls():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert 'src="https://raw.githubusercontent.com/oyvinrog/progress/main/assets/img1.png"' in readme
    assert 'src="https://raw.githubusercontent.com/oyvinrog/progress/main/assets/img2.png"' in readme


def test_docs_page_uses_absolute_screenshot_url():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert 'src="https://raw.githubusercontent.com/oyvinrog/progress/main/assets/screenshot.png"' in html
