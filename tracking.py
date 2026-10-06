"""Local subject tracking and frame-accurate redaction masks."""
import bisect, math, subprocess
import cv2
import numpy as np

def box_at(box, seconds):
    samples = box.get('track', [])
    if not samples:
        return box
    index = max(0, min(len(samples)-1, bisect.bisect_right(samples, seconds, key=lambda s:s['t'])-1))
    return dict(box, **{k:samples[index][k] for k in ('x','y','w','h')})

def motion_fallback(previous, image, rect):
    """Recover a failed correlation tracker using verified local feature motion."""
    old=cv2.cvtColor(previous,cv2.COLOR_BGR2GRAY);new=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    x,y,w,h=map(int,rect);mask=np.zeros_like(old);mask[max(0,y):y+h,max(0,x):x+w]=255
    points=cv2.goodFeaturesToTrack(old,120,.01,4,mask=mask)
    if points is None or len(points)<4:return None
    moved,status,_=cv2.calcOpticalFlowPyrLK(old,new,points,None,winSize=(31,31),maxLevel=3)
    if moved is None:return None
    back,reverse,_=cv2.calcOpticalFlowPyrLK(new,old,moved,None,winSize=(31,31),maxLevel=3)
    if back is None:return None
    valid=(status.ravel()==1)&(reverse.ravel()==1)&(np.linalg.norm(back-points,axis=2).ravel()<1.5)
    if valid.sum()<4:return None
    deltas=(moved-points).reshape(-1,2)[valid];shift=np.median(deltas,axis=0)
    consistent=np.linalg.norm(deltas-shift,axis=1)<3
    if consistent.sum()<4 or consistent.mean()<.6:return None
    shift=np.median(deltas[consistent],axis=0)
    if np.linalg.norm(shift)>max(w,h):return None
    height,width=old.shape;nx=int(round(x+shift[0]));ny=int(round(y+shift[1]))
    if nx<0 or ny<0 or nx+w>width or ny+h>height:return None
    return nx,ny,w,h

def track_subject(video, box, seed_time, progress=lambda p:None, cancelled=lambda:False):
    cap = cv2.VideoCapture(str(video))
    try:
        fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps<=0 or count<1: raise ValueError('Could not read tracking video.')
        first=max(0,math.ceil(box['start']*fps)); last=min(count-1,math.floor(box['end']*fps))
        if last<first: raise ValueError('The box time range contains no frames.')
        seed=max(first,min(last,round(seed_time*fps)))
        cap.set(cv2.CAP_PROP_POS_FRAMES,seed);ok,frame=cap.read()
        if not ok: raise ValueError('Could not read the selected frame.')
        height,width=frame.shape[:2];scale=min(1,720/width);size=(round(width*scale),round(height*scale))
        frame=cv2.resize(frame,size);width,height=size
        initial=(max(0,int(box['x']*width)),max(0,int(box['y']*height)),max(4,int(box['w']*width)),max(4,int(box['h']*height)))
        x,y,w,h=initial;initial=(x,y,min(w,width-x),min(h,height-y))
        samples={};done=0;total=last-first+1
        def save(index,rect):
            nonlocal done
            x,y,w,h=rect;x=max(0,min(width-1,x));y=max(0,min(height-1,y));w=min(w,width-x);h=min(h,height-y)
            samples[index]=dict(t=index/fps,x=x/width,y=y/height,w=w/width,h=h/height)
            done+=1;progress(min(100,round(done/total*100)))
        save(seed,initial)
        for direction,stop in [(1,last),(-1,first)]:
            tracker=cv2.TrackerCSRT_create();tracker.init(frame,initial)
            previous=frame;last_rect=initial
            if direction==1:cap.set(cv2.CAP_PROP_POS_FRAMES,seed+1)
            for index in range(seed+direction,stop+direction,direction):
                if cancelled(): raise InterruptedError('Tracking cancelled.')
                if direction==-1:cap.set(cv2.CAP_PROP_POS_FRAMES,index)
                ok,image=cap.read()
                if not ok:raise ValueError(f'Could not read frame at {index/fps:.2f}s.')
                image=cv2.resize(image,size);ok,rect=tracker.update(image)
                if not ok:
                    rect=motion_fallback(previous,image,last_rect)
                    if rect is None:raise ValueError(f'Subject lost at {index/fps:.2f}s. Pause on a clear frame, draw a close-fitting box with a little margin, and try again. For a scene cut or hidden subject, shorten the box time range. No partial track was applied.')
                    tracker=cv2.TrackerCSRT_create();tracker.init(image,rect)
                save(index,rect)
                previous=image;last_rect=rect
        return [samples[i] for i in sorted(samples)]
    finally:cap.release()

def render_mask(engine, preview, output, boxes, mode, width, height, progress=lambda p:None, cancelled=lambda:False):
    cap=cv2.VideoCapture(str(preview));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));cap.release()
    if fps<=0 or count<1:raise ValueError('Could not read video timing.')
    process=subprocess.Popen([engine,'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-an','-c:v','ffv1',str(output)],stdin=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    try:
        for index in range(count):
            if cancelled():raise InterruptedError('Export cancelled.')
            t=index/fps;mask=np.full((height,width,3),255 if mode=='hide' else 0,np.uint8)
            for box in boxes:
                if not box['start']<=t<=box['end']:continue
                b=box_at(box,t);x=max(0,min(width-1,int(b['x']*width)));y=max(0,min(height-1,int(b['y']*height)))
                right=min(width,math.ceil((b['x']+b['w'])*width));bottom=min(height,math.ceil((b['y']+b['h'])*height))
                mask[y:bottom,x:right]=0 if mode=='hide' else 255
            process.stdin.write(mask.tobytes());progress(round((index+1)/count*100))
        process.stdin.close();error=process.stderr.read();code=process.wait()
        if code:raise ValueError(error.decode(errors='replace'))
    finally:
        if process.poll() is None:process.kill();process.wait()
        if process.stdin and not process.stdin.closed:process.stdin.close()
        process.stderr.close()
