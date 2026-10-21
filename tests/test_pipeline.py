import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from merge import human_data,merge_rows,number,nullable_bool
from parse_input import parse
from match import classify
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'xhs'))
from summarize import summarize

class PipelineTests(unittest.TestCase):
    def test_empty_human_fields(self):
        note='  原话\n第二行，不能润色  '
        output=human_data({}, {'owner_note':note})
        self.assertEqual(output['owner_note'],note)
        for key in ['my_take','best_dish','cuisine_detail','scenario','spicy','price_per_person_cad','skip']:
            self.assertIsNone(output[key])
    def test_zero_and_false_are_explicit_values(self):
        self.assertEqual(number('0'),0)
        self.assertIs(nullable_bool('false'),False)
        self.assertIsNone(nullable_bool(''))
        self.assertIsNone(number(''))
    def test_invalid_fields(self):
        for value in ['nan','inf','-1','4','1.5']:
            with self.assertRaises(ValueError): number(value,0,3,True)
        with self.assertRaises(ValueError): nullable_bool('maybe')
        with self.assertRaises(ValueError): human_data({'scenario':'朋友推荐'}, {})
    def test_merge_missing_api_and_preserve_source_note(self):
        raw=[{'raw_id':'r','name':'店','address':'地址','maps_url':'','owner_note':'  原话  '}]
        matches=[{'raw_id':'r','confirmed':True,'place_id':'id'}]
        rows=merge_rows(raw,matches,[{'place_id':'id','owner_note':'篡改'}],{})
        self.assertEqual(rows[0]['owner_note'],'  原话  ')
        self.assertIsNone(rows[0]['google'])
        self.assertIsNone(rows[0]['spicy'])
        self.assertEqual(merge_rows(raw,[{'raw_id':'r','confirmed':False,'place_id':None}],[],{}),[])
    def test_delimited_bom_multiline_note(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.csv'
            path.write_text('\ufeffName;Address;maps_url;owner_note\n店;123 Main St;;"  原话\nnext  "\n',encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()): rows=parse(path)
            self.assertEqual(rows[0]['owner_note'],'  原话\nnext  ')
    def test_bad_csv_does_not_silently_shift(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.csv';path.write_text('name,address,maps_url,owner_note\nA,B,C,D,E\n')
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError): parse(path)
    def test_name_and_address_both_required(self):
        raw={'raw_id':'r','name':'Cafe','address':'123 Main Street Toronto ON Canada'}
        exact={'id':'a','displayName':{'text':'CAFE'},'formattedAddress':'123 Main St, Toronto, ON, Canada'}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(classify(raw,{'places':[exact]})['confirmed'])
            self.assertTrue(classify(raw,{'places':[exact,dict(exact,id='b')]})['needs_review'])
            self.assertTrue(classify(raw,{'places':[dict(exact,formattedAddress='456 Main St')]})['needs_review'])
            self.assertTrue(classify(raw,{'places':[]})['unresolved'])
            self.assertTrue(classify(raw,{'places':[exact],'nextPageToken':'next'})['needs_review'])
    def test_xhs_manual_denominator(self):
        out=summarize([{'query':'面','label':'明显软广'},{'query':'面','label':'无法判断'},{'query':'面','label':''}])
        self.assertEqual(out['overall']['categories']['明显软广']['share'],.5)
        self.assertEqual(out['overall']['unlabeled'],1)
        self.assertIsNone(summarize([])['overall']['categories']['明显软广']['share'])

if __name__=='__main__': unittest.main()
