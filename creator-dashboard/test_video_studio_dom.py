"""Static Video Studio browser contract: prevent broken selectors after UI refactors.

This is not a substitute for real browser interaction, audio or visual review.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parent
HTML=(ROOT/"static"/"videos.html").read_text(encoding="utf-8")
JS=(ROOT/"static"/"videos.js").read_text(encoding="utf-8")


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.form_depth=0
        self.form_count=0
        self.details_depth=0
        self.min_details_depth=0
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if d.get("id"):
            self.ids.append(d["id"])
        if tag=="form":
            self.form_count+=1
            self.form_depth+=1
        if tag=="details":
            self.details_depth+=1
    def handle_endtag(self, tag):
        if tag=="form":
            self.form_depth-=1
        if tag=="details":
            self.details_depth-=1
            self.min_details_depth=min(self.min_details_depth,self.details_depth)


class VideoStudioDOMTests(unittest.TestCase):
    def test_dom_ids_referenced_in_static_javascript_exist(self):
        html=_Ids();html.feed(HTML);html.close()
        duplicates=[name for name,n in Counter(html.ids).items() if n>1]
        self.assertEqual(duplicates,[],f"Duplicate HTML ids: {duplicates}")
        required=set(re.findall(r"""document\.getElementById\(\s*['"]([\w-]+)['"]\s*\)""",JS))
        missing=sorted(required-set(html.ids))
        self.assertFalse(missing,f"Video Studio JavaScript accesses nonexistent DOM IDs: {missing}")
        self.assertGreater(len(required),30)
        self.assertEqual(html.form_count,1)
        self.assertEqual(html.form_depth,0)
        self.assertEqual(html.details_depth,0)
        self.assertEqual(html.min_details_depth,0)

    def test_one_click_form_and_safe_manual_alternatives_remain(self):
        ids=set(_Ids.__dict__)  # dummy names are not used as actual UI controls
        doc=_Ids();doc.feed(HTML)
        values=set(doc.ids)
        for field in ("topicInput","creativeBriefInput","quickAutoMedia","quickAutoRender",
                      "quickResearch","captionStyleSelect","quickStyleButtons",
                      "templatePicker","mediaLibraryPanel","studioAdvanced",
                      "testVoiceBtn","engineSelect","scriptInput","videoForm"):
            with self.subTest(control=field):
                self.assertIn(field,values)
        self.assertIn("autoRender: document.getElementById('quickAutoRender').checked",JS)
        self.assertIn("autoMedia: document.getElementById('quickAutoMedia').checked",JS)


if __name__=="__main__":
    unittest.main()
