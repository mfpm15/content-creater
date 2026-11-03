import io
import json
import os
import unittest
from unittest.mock import patch

import router_research
import research_service


class RouterResearchTests(unittest.TestCase):
    def run_search(self, catalogue, response, env=None):
        requests=[]
        def opened(request, timeout):
            requests.append(request)
            return io.BytesIO(json.dumps(catalogue if len(requests)==1 else response).encode())
        with patch.dict(os.environ,env or {},clear=True),patch.object(router_research,'open_authenticated',side_effect=opened):
            result=research_service.research('Topik','Konteks',scope='article')
        return result,requests

    def test_discovery_search_and_provenance_use_article_gateway(self):
        result,requests=self.run_search({'data':[{'kind':'webSearch','id':'search-one'}]},
            {'results':[{'url':'https://example.org/a','title':'Sumber','snippet':'Bukti 25%'},
                        {'url':'https://example.org/a'}, {'url':'javascript:alert(1)'}]},
            {'ARTICLE_LLM_BASE_URL':'https://gateway.example/v1','ARTICLE_LLM_API_KEY':'fake-key'})
        self.assertEqual([r.full_url for r in requests],['https://gateway.example/v1/models/web','https://gateway.example/v1/search'])
        self.assertEqual(requests[1].get_header('Authorization'),'Bearer fake-key')
        self.assertEqual(json.loads(requests[1].data)['model'],'search-one')
        self.assertEqual(result['sourceCount'],1)
        self.assertFalse(result['verified'])
        self.assertIn('Bukti 25%',result['summary'])

    def test_ambiguous_routes_require_explicit_selection(self):
        with self.assertRaisesRegex(RuntimeError,'RESEARCH_SEARCH_MODEL'):
            self.run_search({'data':[{'kind':'webSearch','id':'a'},{'kind':'webSearch','id':'b'}]}, {})

    def test_chat_answer_without_search_results_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'tidak menghasilkan sumber'):
            self.run_search({'data':[{'kind':'webSearch','id':'a'}]}, {'answer':'A plausible answer with a URL'})

    def test_chat_model_is_not_a_search_route(self):
        with self.assertRaisesRegex(RuntimeError,'0 pilihan'):
            self.run_search({'data':[{'kind':'chat','id':'ag/gemini'}]}, {})

    def test_explicit_google_does_not_fallback_to_router(self):
        with patch.dict(os.environ,{'RESEARCH_PROVIDER':'google'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'GOOGLE_API_KEY'):
                research_service.research('Topic','')

    def test_invalid_catalogue_and_provider_fail(self):
        with self.assertRaisesRegex(RuntimeError,'Katalog'):
            self.run_search({'data':'bad'}, {})
        with patch.dict(os.environ,{'RESEARCH_PROVIDER':'invalid'},clear=True):
            with self.assertRaises(ValueError):research_service.provider()
