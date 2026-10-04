"""Integration checks using synthetic footage; no personal video files required."""
import pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from simple_video_redactor import engine,export_command

class ExportTests(unittest.TestCase):
    def test_crop_trim_preserves_original_redaction_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            source=pathlib.Path(folder)/'source.mp4';output=pathlib.Path(folder)/'redacted.mp4'
            subprocess.run([engine(),'-y','-v','error','-f','lavfi','-i','testsrc2=size=320x240:rate=25:duration=4','-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
            boxes=[dict(x=.25,y=.25,w=.5,h=.5,start=1.5,end=2.5)]
            command=export_command(source,output,boxes,'keep',False,320,240,dict(x=.125,y=.125,w=.75,h=.75),(1,3))
            subprocess.run(command,check=True,capture_output=True)
            probe=subprocess.run([engine(),'-hide_banner','-i',str(output)],capture_output=True).stderr.decode(errors='replace')
            self.assertIn('240x180',probe);self.assertIn('00:00:02.00',probe);self.assertIn('Audio:',probe)
            for time,visible in [(.24,False),(1.,True),(1.76,False)]:
                pixels=subprocess.check_output([engine(),'-v','error','-ss',str(time),'-i',str(output),'-frames:v','1','-vf','scale=100:100','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
                self.assertEqual(max(pixels)>30,visible);self.assertLess(max(pixels[:3]),10)
            for mode in ['keep','hide']:
                boxes=[dict(x=.25,y=.25,w=.5,h=.5,start=0,end=4)]
                subprocess.run(export_command(source,output,boxes,mode,True,320,240),check=True,capture_output=True)
                pixels=subprocess.check_output([engine(),'-v','error','-ss','1','-i',str(output),'-frames:v','1','-vf','scale=100:100','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
                index=0 if mode=='keep' else (50*100+50)*3
                self.assertLess(max(pixels[index:index+3]),10);self.assertGreater(max(pixels),30)

if __name__=='__main__':unittest.main()
