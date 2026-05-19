import json
from pathlib import Path

from app.adapter.importer.gemini_importer import parse_takeout


def test_parse_takeout_decodes_html_entities(tmp_path: Path) -> None:
    takeout_path = tmp_path / "Gemini.json"
    takeout_path.write_text(
        json.dumps(
            [
                {
                    "time": "2026-05-18T12:00:00Z",
                    "title": "Redis &amp; Elasticsearch",
                    "safeHtmlItem": [
                        {
                            "html": (
                                "<p>Search &#39;safety&#39; and "
                                "&quot;fallback&quot; are explained.</p>"
                                "<p>Redis &amp; Elasticsearch</p>"
                            )
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    conversations = parse_takeout(takeout_path)

    assert len(conversations) == 1
    assert [(m["role"], m["content"]) for m in conversations[0].messages] == [
        ("user", "Redis & Elasticsearch"),
        ("assistant", "Search 'safety' and \"fallback\" are explained.\n\nRedis & Elasticsearch"),
    ]
