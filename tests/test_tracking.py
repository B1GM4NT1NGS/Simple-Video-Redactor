"""Moving-subject tracking and burned-in export checks on synthetic footage."""
import pathlib, tempfile, unittest, subprocess, sys
import cv2
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from tracking import track_subject, box_at, render_mask
from simple_video_redactor import engine, export_command

class TrackingTests(unittest.TestCase):
    def test_moving_subject_preview_mask_and_both_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=pathlib.Path(folder);source=folder/'moving.avi'
            writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
            texture=np.random.default_rng(10).integers(50,255,(48,48,3),dtype=np.uint8)
            for i in range(30):
                frame=np.full((240,320,3),35,np.uint8);x=30+i*4;frame[80:128,x:x+48]=texture;writer.write(frame)
            writer.release()
            box=dict(x=30/320,y=80/240,w=48/320,h=48/240,start=0,end=2.9)
            samples=track_subject(source,box,0)
            self.assertEqual(len(samples),30)
            self.assertAlmostEqual(samples[-1]['x']*320,146,delta=10)
            box['track']=samples
            # A seed in the middle must also track earlier frames.
            seed=dict(box_at(box,1.5));seed.pop('track')
            reverse=track_subject(source,seed,1.5)
            self.assertAlmostEqual(reverse[0]['x']*320,30,delta=12)
            for mode in ['hide','keep']:
                mask=folder/(mode+'.mkv');out=folder/(mode+'.mp4')
                render_mask(engine(),source,mask,[box],mode,320,240)
                subprocess.run(export_command(source,out,[box],mode,True,320,240,trim=(.5,2.5),mask=mask),check=True,capture_output=True)
                for t in [.2,1.7]:
                    image=np.frombuffer(subprocess.check_output([engine(),'-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(240,320,3)
                    b=box_at(box,t+.5);x=int((b['x']+b['w']/2)*320);y=int((b['y']+b['h']/2)*240)
                    self.assertEqual(int(image[y,x].max())<15,mode=='hide')
                    self.assertEqual(int(image[10,10].max())<15,mode=='keep')
            with self.assertRaises(InterruptedError):track_subject(source,seed,1.5,cancelled=lambda:True)

if __name__=='__main__':unittest.main()
