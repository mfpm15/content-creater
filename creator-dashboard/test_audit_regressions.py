import unittest
from unittest.mock import patch
import article_drafter as ad
import video_delivery


class AuditRegressions(unittest.TestCase):
    def test_expansion_keeps_source_evidence(self):
        inp=ad.clean_input({'title':'Audit','points':'Catatan konteks unik','sources':'Bukti sumber unik','words':1000})
        outline={'title':'Audit','sections':[{'heading':'Bagian','goal':'Jelaskan','subheadings':[],'words':400}], 'images':[]}
        prompts=[]
        def ask(system,user,normalizer,model=None):
            prompts.append(user)
            return [{'type':'p','text':'Pendek.'}]
        with patch.object(ad,'_ask_json',side_effect=ask):
            ad.write_section(inp,outline,{'references':['Sumber']},0)
        self.assertEqual(len(prompts),2)
        self.assertIn('Bukti sumber unik',prompts[1])
        self.assertIn('Catatan konteks unik',prompts[1])

    def test_invalid_measurements_never_pass_delivery(self):
        for value in (float('nan'),float('inf'),-1,0):
            reports=video_delivery.evaluate({'width':1080,'height':1920,'avg_frame_rate':'30/1'},value,{'status':'measured','integrated_lufs':float('nan'),'true_peak_dbfs':-1})
            for row in reports.values():
                self.assertEqual(row['status'],'needs_attention')
                self.assertIn('loudness_unmeasured',{i['code'] for i in row['issues']})

    def test_rewrite_guard_distinguishes_signed_numbers(self):
        import article_tools
        from collections import Counter
        tokens=lambda text:Counter(m.group(0) for m in article_tools.PROTECTED.finditer(text))
        for before,after in [('Turun -3,5%', 'Turun 3,5%'),('Nilai +2','Nilai -2'),('Rp-2.000','Rp2.000')]:
            self.assertNotEqual(tokens(before),tokens(after))

    def test_citation_ranges_are_shared_by_writer_and_audit(self):
        import evidence
        text='Hasil 25% [1–3; 5].'
        self.assertEqual(ad.sanitize_citations(text,5),text)
        report=evidence.audit({'blocks':[{'type':'p','text':text}],'references':['a','b','c','d','e']})
        self.assertEqual(report['diagnostics']['uncited_references'],[4])
        self.assertEqual(report['claims'][0]['numbers_absent_from_excerpts'],['25%'])
        self.assertEqual(report['claims'][0]['unknown_citations'],[])
        for citation in ('[3-1]','[1-9999999]','[1-2-3]'):
            self.assertEqual(ad.sanitize_citations(citation,5),'[PERLU VERIFIKASI]')
            audited=evidence.audit({'blocks':[{'type':'p','text':citation}]})
            self.assertTrue(audited['claims'][0]['invalid_citation_range'])

    def test_research_worker_uses_dashboard_environment(self):
        import os
        import research_service
        from types import SimpleNamespace
        from pathlib import Path
        with patch.dict(os.environ,{'GOOGLE_API_KEY':'test-only'}), patch('pathlib.Path.is_file',return_value=True), patch.object(research_service.subprocess,'run',return_value=SimpleNamespace(stdout='{"sources":[{"url":"https://example.org"}]}',returncode=0)) as run:
            result=research_service.research('Topik','Konteks')
            self.assertTrue(result['sources'])
            expected=research_service.resolve_python(Path(research_service.__file__).resolve().parent)
            self.assertEqual(run.call_args.args[0][0],str(expected))
            self.assertNotIn('podcastfy',run.call_args.args[0][0])

    def test_local_check_reports_missing_dependencies_without_network(self):
        import local_check
        with patch.object(local_check,'command_ok',return_value=False),patch.object(local_check,'find_browser',return_value=None):
            result=local_check.inspect()
        self.assertFalse(result['ok'])
        self.assertTrue(any(row['check']=='Chrome/Edge' and row['status']=='missing' for row in result['checks']))

    def test_explicit_web_research_never_silently_downgrades(self):
        import os
        import video_drafter
        with patch.dict(os.environ,{'RESEARCH_PROVIDER':'google'},clear=True), patch.object(video_drafter.threading.Thread,'start') as start:
            with self.assertRaisesRegex(ValueError,'Riset web belum siap'):
                video_drafter.start_job({'topic':'Audit','researchMode':'web','script':'Naskah tersedia'})
            start.assert_not_called()
