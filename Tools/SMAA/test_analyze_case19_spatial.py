import hashlib, tempfile, unittest
from pathlib import Path
from analyze_case19_spatial import analyze, METRICS
from verify_case19_spatial import MODES, CASE18
class TimingValidation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'results.csv'
    def fixture(self):
        text='Case19 spatial cost matrix\nPNG/query/readback Off\nAPI:  DirectX11\nVsync:        OFF\nFullscreen:   Windowed\nResolution: 1920 x 1061\n'
        text+='edge_storage,O-T2X-R,49,PASS\n' # Native4 precondition, outside measured repeats.
        for mode_index,mode in enumerate(MODES):
            for run in range(6):
                text+=f'edge_storage,{mode},{28 if "Case19-EdgeRGBA8" in mode else 49},PASS\n'
                for metric in sorted(METRICS):
                    v=1+mode_index*.1+run*.01
                    text+=f'timing,{mode},{run},{metric},4800,{v},{v},{v},{v},0.1,60\n'
        return text+'Aggregate: PASS\n'
    def receipt(self,text):
        self.path.write_text(text,encoding='utf-8')
        return dict(phase='Benchmark',report=str(self.path),report_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
    def test_complete_paired_matrix(self):
        result=analyze(self.receipt(self.fixture()))
        self.assertEqual(result['validation'],'PASS')
        self.assertEqual(result['repeats'],6)
        self.assertIn(f'{MODES[-1]} vs {CASE18}',result['paired'])
    def test_missing_repeat_metric(self):
        text=self.fixture().splitlines();i=next(i for i,l in enumerate(text) if l.startswith('timing,'))
        del text[i]
        with self.assertRaisesRegex(ValueError,'Missing/duplicate'):analyze(self.receipt('\n'.join(text)))
    def test_duplicate_row(self):
        text=self.fixture();row=next(l for l in text.splitlines() if l.startswith('timing,'))
        with self.assertRaisesRegex(ValueError,'Missing/duplicate'):analyze(self.receipt(text+row+'\n'))
    def test_wrong_actual_format(self):
        text=self.fixture().replace('edge_storage,O-T2X-R,49,PASS','edge_storage,O-T2X-R,28,PASS',1)
        with self.assertRaisesRegex(ValueError,'Incorrect actual'):analyze(self.receipt(text))
    def test_missing_precondition_format(self):
        text=self.fixture().replace('edge_storage,O-T2X-R,49,PASS\n','',1)
        with self.assertRaisesRegex(ValueError,'Missing actual'):analyze(self.receipt(text))
    def test_incomplete_frame_count(self):
        text=self.fixture().replace(',4800,',',4799,',1)
        with self.assertRaisesRegex(ValueError,'sample counts'):analyze(self.receipt(text))
    def test_changed_report(self):
        r=self.receipt(self.fixture());self.path.write_text(self.fixture()+'changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'SHA'):analyze(r)
if __name__=='__main__':unittest.main()
