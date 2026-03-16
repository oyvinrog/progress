from pathlib import Path


def test_readme_uses_absolute_image_urls():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert 'src="https://github.com/oyvinrog/progress/blob/master/assets/img1.png?raw=1"' in readme
    assert 'src="https://github.com/oyvinrog/progress/blob/master/assets/img2.png?raw=1"' in readme


def test_docs_page_uses_absolute_screenshot_url():
    html = Path("docs/index.html").read_text(encoding="utf-8")
    assert 'src="https://github.com/oyvinrog/progress/blob/master/assets/screenshot.png?raw=1"' in html
