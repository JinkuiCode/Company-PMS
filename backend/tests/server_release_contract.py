"""Release provenance and runtime-data exclusion using an isolated Git fixture."""
import hashlib,json,os,shutil,subprocess,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class ReleaseContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pms-release-contract-')
        self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        self.env=os.environ.copy();self.bin=Path(self.temp.name)/'bin';self.bin.mkdir()
        # Simulated builder deliberately uses both the entry HTML and source.
        npm=self.bin/'npm';npm.write_text('#!/bin/sh\nset -eu\nmkdir -p dist\ncat index.html src/main.js > dist/index.html\n')
        npm.chmod(0o755);self.env['PATH']=str(self.bin)+os.pathsep+self.env['PATH']
        self.git('init','-q');self.git('config','user.name','Release fixture');self.git('config','user.email','fixture@example.invalid')
        files={'backend/app/core/config.py':'fixture config','backend/main.py':'fixture main','backend/requirements.txt':'fixture deps','backend/scripts/check.py':'fixture check','backend/vendor/k3cloud_webapi_sdk-3.0.0-py3-none-any.whl':'fixture wheel','backend/.env.kingdee.example':'K3_READ_ONLY=true','backend/.env.example':'PMS_ENV=production','frontend/index.html':'ENTRY_A\n','frontend/src/main.js':'SOURCE_A\n','frontend/tsconfig.json':'{}','frontend/package.json':'{}','frontend/public/a.txt':'public','ops/windows/Start-Pms.ps1':'fixture ops','docs/PMS服务器发布与回退说明.md':'部署前只读核对与回退','frontend/package-lock.json':'{}'}
        for name,value in files.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
        shutil.copy2(ROOT/'build-server-release.command',self.root/'build-server-release.command')
        (self.root/'.gitignore').write_text('frontend/node_modules/\nfrontend/dist/\nbackend/data/\nbackend/.env.local\nrelease/\n')
        (self.root/'frontend/node_modules').mkdir();self.commit('A')
        (self.root/'frontend/dist').mkdir();(self.root/'frontend/dist/index.html').write_text('STALE_BUILD')
        (self.root/'backend/.env.local').write_text('FAKE_SECRET_NEVER_PACKAGE')
        (self.root/'backend/data').mkdir();(self.root/'backend/data/db.sqlite').write_text('FAKE_DB')
    def tearDown(self):self.temp.cleanup()
    def git(self,*args):
        r=subprocess.run(['git',*args],cwd=self.root,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);return r.stdout.strip()
    def commit(self,message):self.git('add','.');self.git('commit','-qm',message)
    def build(self,*args):
        return subprocess.run([str(self.root/'build-server-release.command'),*args],cwd=self.root,env=self.env,capture_output=True,text=True)
    def test_no_skip_build_escape_hatch(self):
        r=self.build('--skip-build');self.assertNotEqual(r.returncode,0)
    def test_relative_output_and_bundle_integrity(self):
        r=self.build('--output-dir','release');self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        archive=next((self.root/'release').glob('*.zip'));self.assertEqual(archive.with_suffix('.zip.sha256').read_text().split()[0],hashlib.sha256(archive.read_bytes()).hexdigest())
        with zipfile.ZipFile(archive) as z:
            names=z.namelist();prefix=names[0].split('/')[0]+'/'
            for name in ['backend/main.py','backend/requirements.txt','backend/app/core/config.py','backend/.env.example','frontend/dist/index.html','ops/windows/Start-Pms.ps1','RELEASE-MANIFEST.txt','SERVER-DEPLOYMENT.md','SHA256SUMS']:
                self.assertIn(prefix+name,names)
            for name in names:self.assertTrue({'.env.local','.git','data','node_modules','tests','__pycache__'}.isdisjoint(Path(name).parts))
            self.assertIn(self.git('rev-parse','HEAD'),z.read(prefix+'RELEASE-MANIFEST.txt').decode())
            for line in z.read(prefix+'SHA256SUMS').decode().splitlines():
                digest,name=line.split(maxsplit=1);self.assertEqual(digest,hashlib.sha256(z.read(prefix+name)).hexdigest())
    def test_new_commit_rebuilds_frontend_not_stale_dist(self):
        (self.root/'frontend/src/main.js').write_text('SOURCE_B\n');self.commit('B')
        out=Path(self.temp.name)/'out';r=self.build('--output-dir',str(out));self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        with zipfile.ZipFile(next(out.glob('*.zip'))) as z:
            index=next(n for n in z.namelist() if n.endswith('/frontend/dist/index.html'))
            self.assertIn(b'SOURCE_B',z.read(index));self.assertNotIn(b'STALE_BUILD',z.read(index))
    def test_dirty_entry_and_compiler_config_rejected(self):
        for name in ['frontend/index.html','frontend/tsconfig.json']:
            with self.subTest(name=name):
                p=self.root/name;original=p.read_text();p.write_text('UNCOMMITTED')
                r=self.build('--output-dir',str(Path(self.temp.name)/'out'));self.assertNotEqual(r.returncode,0)
                p.write_text(original)
    def test_dirty_backend_rejected(self):
        (self.root/'backend/main.py').write_text('UNCOMMITTED');self.assertNotEqual(self.build().returncode,0)
    def test_untracked_build_input_rejected(self):
        (self.root/'frontend/new-config.json').write_text('{}');self.assertNotEqual(self.build().returncode,0)

if __name__=='__main__':unittest.main()
