"""Small checks for graph direction and unsupported cases, not benchmark evidence."""
import unittest
from analyze import inspect_document

def doc(nodes, edges):
    return {'workflow': {'id':0,'name':'fixture','workflow':{'nodes':nodes,'connections':{
        a:{'main':[[{'node':b} for b in bs]]} for a,bs in edges.items()}}}}

def n(name,typ,p=None):
    return {'name':name,'type':typ,'parameters':p or {}}

class InventoryTest(unittest.TestCase):
    def test_late_download_is_flag_not_collision(self):
        nodes=[n('a','@n8n/n8n-nodes-langchain.agent'),n('f','n8n-nodes-base.googleDrive',{'operation':'download'}),
               n('s','n8n-nodes-base.gmail',{'operation':'send','options':{'attachmentsUi':{'attachmentsBinary':[{'property':'data'}]}}})]
        r=inspect_document(doc(nodes,{'a':['f'],'f':['s']}),'fixture')
        self.assertEqual(r['late_file_paths'][0]['earlier_ai_nodes'],['a'])
        self.assertEqual(r['late_file_paths'][0]['intervening_ai_nodes'],[])
        self.assertEqual(r['sage_status'],'not_modeled')

    def test_ai_after_file_must_not_be_clean_context_evidence(self):
        nodes=[n('f','n8n-nodes-base.googleDrive',{'operation':'download'}),n('a','@n8n/n8n-nodes-langchain.agent'),
               n('s','n8n-nodes-base.gmail',{'options':{'attachmentsUi':{'x':1}}})]
        r=inspect_document(doc(nodes,{'f':['a'],'a':['s']}),'fixture')
        self.assertEqual(r['late_file_paths'][0]['intervening_ai_nodes'],['a'])

    def test_broken_reference_is_reported(self):
        r=inspect_document(doc([n('a','n8n-nodes-base.set',{'value':"$('absent').item.json"})],{'a':['absent']}),'fixture')
        self.assertEqual(len(r['unresolved_references']),2)

if __name__=='__main__':
    unittest.main()
