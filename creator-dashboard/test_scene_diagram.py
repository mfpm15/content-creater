import unittest
import lottie_adapter
import remotion_adapter
import scene_diagram
import video_drafter as vd

class DiagramTests(unittest.TestCase):
    def test_approved_labels_survive_normalization_and_both_exports(self):
        diagram={'kind':'process','labels':['Riset','Review','Terbit']}
        plan=vd.normalize_scene_plan({'scenes':[{'start':0,'end':3,'narration':'Riset, review, lalu terbit.',
            'onScreenText':'Alur produksi','diagram':diagram}]},'Produksi','',3)
        self.assertEqual(plan['scenes'][0]['diagram'],diagram)
        props,_=remotion_adapter.manifest(plan,{'width':1080,'height':1920})
        self.assertEqual(props['shots'][0]['diagram'],diagram)
        animation=lottie_adapter.build(plan,{'width':1080,'height':1920})
        labels=[layer['t']['d']['k'][0]['s']['t'] for layer in animation['layers'] if '-label-' in layer['nm']]
        self.assertEqual(labels,diagram['labels'])
        self.assertEqual(len({l['ind'] for l in animation['layers']}),len(animation['layers']))

    def test_bad_diagram_fails_before_render(self):
        for value in (None,{}, {'kind':'process','labels':['a']},{'kind':'comparison','labels':['a','b','c']},
                      {'kind':'process','labels':['a','x'*49]},{'kind':'process','labels':['a','b\n']},
                      {'kind':'process','labels':['a','b'],'script':'bad'}):
            with self.subTest(value=value),self.assertRaises(ValueError):scene_diagram.validate(value)
