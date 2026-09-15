"""Offline checks for archive traversal, symlink and overwrite rejection."""
from pathlib import Path
import io,stat,sys,tempfile,unittest,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reproduce import safe_extract

class ArchiveGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def make(self,names):
        p=self.root/'input.zip'
        with zipfile.ZipFile(p,'w') as z:
            for n in names:z.writestr(n,b'example')
        return p
    def test_valid_nested_archive(self):
        dest=self.root/'new output'
        safe_extract(self.make(['nested/file.txt']),dest)
        self.assertEqual((dest/'nested/file.txt').read_bytes(),b'example')
    def test_parent_traversal(self):
        dest=self.root/'new'
        with self.assertRaises(ValueError):safe_extract(self.make(['../outside.txt']),dest)
        self.assertFalse(dest.exists());self.assertFalse((self.root/'outside.txt').exists())
    def test_absolute_and_drive_names(self):
        for name in ['/absolute.txt','C:/absolute.txt','C:\\absolute.txt']:
            with self.subTest(name=name),self.assertRaises(ValueError):
                safe_extract(self.make([name]),self.root/'new')
    def test_case_duplicate(self):
        with self.assertRaises(ValueError):safe_extract(self.make(['file.txt','FILE.txt']),self.root/'new')
    def test_symlink(self):
        p=self.root/'link.zip';entry=zipfile.ZipInfo('link');entry.create_system=3
        entry.external_attr=(stat.S_IFLNK|0o777)<<16
        with zipfile.ZipFile(p,'w') as z:z.writestr(entry,'../outside')
        with self.assertRaises(ValueError):safe_extract(p,self.root/'new')
    def test_no_existing_output(self):
        dest=self.root/'old';dest.mkdir();(dest/'keep').write_text('original')
        with self.assertRaises(ValueError):safe_extract(self.make(['keep']),dest)
        self.assertEqual((dest/'keep').read_text(),'original')

if __name__=='__main__':unittest.main()
