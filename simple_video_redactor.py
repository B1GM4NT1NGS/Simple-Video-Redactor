import sys, pathlib, tempfile, shutil, re, json, subprocess
from PySide6.QtCore import Qt,QUrl,QRectF,QPointF,QProcess,Signal,QThread,QSize
from PySide6.QtGui import QPainter,QColor,QPen,QImage,QDesktopServices
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QFileDialog,QComboBox,QCheckBox,QSlider,QListWidget,QDoubleSpinBox,QMessageBox,QDialog,QStyledItemDelegate,QStyle,QListWidgetItem
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QVideoSink

def engine():
    if getattr(sys,'frozen',False): return str(pathlib.Path(sys._MEIPASS)/'ffmpeg.exe')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

from tracking import box_at, track_subject, render_mask

class BackgroundJob(QThread):
    progress=Signal(int)
    result=Signal(object)
    failed=Signal(str)
    def __init__(self, task, parent):
        super().__init__(parent);self.task=task
    def run(self):
        try:self.result.emit(self.task(self.progress.emit,self.isInterruptionRequested))
        except Exception as error:self.failed.emit(str(error))

def export_command(source,output,boxes,mode,mute,width,height,crop=None,trim=None,mask=None):
    cmd=[engine(),'-y','-noautorotate','-i',str(source)]
    regions=[]
    for b in boxes:
        x=max(0,min(width-1,int(b['x']*width)));y=max(0,min(height-1,int(b['y']*height)))
        w=max(1,min(width-x,int(b['w']*width+.999)));h=max(1,min(height-y,int(b['h']*height+.999)))
        regions.append((x,y,w,h,b['start'],b['end']))
    final_filters=[]
    if crop:
        x=max(0,min(width-2,int(crop['x']*width)));y=max(0,min(height-2,int(crop['y']*height)))
        w=max(2,min(width-x,int(crop['w']*width)));h=max(2,min(height-y,int(crop['h']*height)))
        final_filters.append(f'crop={w}:{h}:{x}:{y}:exact=1')
    if trim:final_filters += [f"trim=start={trim[0]}:end={trim[1]}",'setpts=PTS-STARTPTS']
    final_filters += ['scale=trunc(iw/2)*2:trunc(ih/2)*2','setsar=1']
    if mask:
        cmd += ['-i',str(mask)]
        parts=['[0:v:0]format=gbrp,split[original][blacksrc]','[blacksrc]lutrgb=r=0:g=0:b=0[black]','[1:v:0]format=gbrp[mask]','[black][original][mask]maskedmerge[merged]','[merged]'+','.join(final_filters)+'[out]']
        cmd += ['-filter_complex',';'.join(parts),'-map','[out]']
    elif mode=='keep':
        parts=['[0:v:0]format=rgb24,split='+str(len(regions)+1)+'[base]'+''.join(f'[s{i}]' for i in range(len(regions))), '[base]drawbox=0:0:iw:ih:black:t=fill[b0]']
        for i,(x,y,w,h,start,end) in enumerate(regions):
            parts += [f'[s{i}]crop={w}:{h}:{x}:{y}:exact=1[c{i}]',f"[b{i}][c{i}]overlay={x}:{y}:format=rgb:enable='between(t,{start},{end})'[b{i+1}]"]
        parts.append(f'[b{len(regions)}]'+','.join(final_filters)+'[out]')
        cmd += ['-filter_complex',';'.join(parts),'-map','[out]']
    else:
        filters=[f"drawbox={x}:{y}:{w}:{h}:black:t=fill:enable='between(t,{start},{end})'" for x,y,w,h,start,end in regions]
        cmd+=['-vf',','.join(filters+final_filters),'-map','0:v:0']
    if not mute:
        cmd+=['-map','0:a:0?']
        if trim:cmd+=['-af',f'atrim=start={trim[0]}:end={trim[1]},asetpts=PTS-STARTPTS']
    return cmd+['-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-map_metadata','-1','-metadata:s:v:0','rotate=0','-movflags','+faststart',str(output)]

class Screen(QWidget):
    changed=Signal()
    def __init__(self,window):
        super().__init__();self.owner=window;self.image=QImage();self.target=QRectF();self.drag=None;self.draw=True
        self.setMinimumSize(480,300);self.setMouseTracking(True)
    def frame(self,frame):
        image=frame.toImage()
        if not image.isNull():
            self.image=image;self.update()
            if getattr(self.owner,'need_first',False):self.owner.need_first=False;self.owner.player.pause()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#080b10'))
        if self.image.isNull():
            p.setPen(QColor('#9faec3'));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Import a video to begin');return
        size=self.image.size();size.scale(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
        self.target=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height());p.drawImage(self.target,self.image)
        o=self.owner;active=[box_at(b,o.player.position()/1000) for b in o.boxes if b['start']<=o.player.position()/1000<=b['end']]
        def rect(b):return QRectF(self.target.x()+b['x']*self.target.width(),self.target.y()+b['y']*self.target.height(),b['w']*self.target.width(),b['h']*self.target.height())
        if o.clean.isChecked() and not self.drag and o.boxes:
            if o.mode.currentIndex()==0:
                p.fillRect(self.target,Qt.GlobalColor.black)
                for b in active:
                    r=rect(b);src=QRectF(b['x']*self.image.width(),b['y']*self.image.height(),b['w']*self.image.width(),b['h']*self.image.height());p.drawImage(r,self.image,src)
            else:
                for b in active:p.fillRect(rect(b),Qt.GlobalColor.black)
        else:
            for i,b in enumerate(o.boxes):
                r=rect(box_at(b,o.player.position()/1000));p.setPen(QPen(QColor('#72dfb6') if i==o.selected else QColor('white'),2));p.drawRect(r);p.fillRect(QRectF(r.right()-7,r.bottom()-7,8,8),p.pen().color());p.drawText(r.adjusted(7,3,0,0),str(i+1))
    def point(self,event):
        r=self.target;return QPointF(max(0,min(1,(event.position().x()-r.x())/r.width())),max(0,min(1,(event.position().y()-r.y())/r.height())))
    def mousePressEvent(self,event):
        o=self.owner
        if not o.source or o.busy or self.image.isNull() or not self.target.contains(event.position()):return
        o.player.pause();p=self.point(event);self.drag=None
        if not self.draw:
            for i in reversed(range(len(o.boxes))):
                b=o.boxes[i];current=box_at(b,o.player.position()/1000);b.update({k:current[k] for k in ('x','y','w','h')})
                if abs(p.x()-b['x']-b['w'])<14/self.target.width() and abs(p.y()-b['y']-b['h'])<14/self.target.height():self.drag=('resize',p,dict(b));o.selected=i;break
                if b['x']<=p.x()<=b['x']+b['w'] and b['y']<=p.y()<=b['y']+b['h']:self.drag=('move',p,dict(b));o.selected=i;break
        if not self.drag:
            o.selected=len(o.boxes);o.boxes.append(dict(x=p.x(),y=p.y(),w=0,h=0,start=0,end=o.player.duration()/1000));self.drag=('draw',p,None)
        o.clean.setChecked(False);self.update()
    def mouseMoveEvent(self,event):
        if not self.drag:return
        kind,start,original=self.drag;p=self.point(event);b=self.owner.boxes[self.owner.selected]
        if b.get('track'):b.pop('track',None);self.owner.status.setText('Track cleared after box adjustment. Click Track selected subject to retrack from this frame.')
        if kind=='draw':b.update(x=min(p.x(),start.x()),y=min(p.y(),start.y()),w=abs(p.x()-start.x()),h=abs(p.y()-start.y()))
        elif kind=='move':b.update(x=max(0,min(1-b['w'],original['x']+p.x()-start.x())),y=max(0,min(1-b['h'],original['y']+p.y()-start.y())))
        else:b.update(w=max(.005,min(1-b['x'],p.x()-b['x'])),h=max(.005,min(1-b['y'],p.y()-b['y'])))
        self.update()
    def mouseReleaseEvent(self,event):
        if self.drag:
            b=self.owner.boxes[self.owner.selected]
            if b['w']*self.target.width()<3 or b['h']*self.target.height()<3:self.owner.boxes.pop(self.owner.selected);self.owner.selected=-1
            self.drag=None;self.draw=False;self.changed.emit();self.update()

class CropScreen(Screen):
    def __init__(self,dialog):
        super().__init__(dialog);self.crop=dict(x=0.,y=0.,w=1.,h=1.);self.crop_drag=None;self.setMinimumSize(480,280)
    def crop_rect(self):
        r=self.target;b=self.crop;return QRectF(r.x()+b['x']*r.width(),r.y()+b['y']*r.height(),b['w']*r.width(),b['h']*r.height())
    def paintEvent(self,event):
        super().paintEvent(event)
        if self.image.isNull():return
        p=QPainter(self);r=self.target;box=self.crop_rect();shade=QColor(0,0,0,170)
        for area in [QRectF(r.left(),r.top(),r.width(),box.top()-r.top()),QRectF(r.left(),box.bottom(),r.width(),r.bottom()-box.bottom()),QRectF(r.left(),box.top(),box.left()-r.left(),box.height()),QRectF(box.right(),box.top(),r.right()-box.right(),box.height())]:p.fillRect(area,shade)
        p.setPen(QPen(QColor('#ffdd00'),2));p.drawRect(box)
        p.setPen(QPen(QColor(255,255,255,100),1))
        for f in [1/3,2/3]:p.drawLine(QPointF(box.left()+box.width()*f,box.top()),QPointF(box.left()+box.width()*f,box.bottom()));p.drawLine(QPointF(box.left(),box.top()+box.height()*f),QPointF(box.right(),box.top()+box.height()*f))
        for pt in [box.topLeft(),box.topRight(),box.bottomLeft(),box.bottomRight()]:p.fillRect(QRectF(pt.x()-6,pt.y()-6,12,12),QColor('#ffdd00'))
    def mousePressEvent(self,event):
        if self.image.isNull() or not self.target.adjusted(-12,-12,12,12).contains(event.position()):return
        self.owner.player.pause();p=self.point(event);b=self.crop;corners={'tl':(b['x'],b['y']),'tr':(b['x']+b['w'],b['y']),'bl':(b['x'],b['y']+b['h']),'br':(b['x']+b['w'],b['y']+b['h'])}
        nearest=min(corners,key=lambda key:((p.x()-corners[key][0])*self.target.width())**2+((p.y()-corners[key][1])*self.target.height())**2)
        cx,cy=corners[nearest];distance=((p.x()-cx)*self.target.width())**2+((p.y()-cy)*self.target.height())**2
        if distance<900:self.crop_drag=(nearest,p,dict(b))
        elif self.crop_rect().contains(event.position()):self.crop_drag=('move',p,dict(b))
    def mouseMoveEvent(self,event):
        if not self.crop_drag:return
        kind,start,old=self.crop_drag;p=self.point(event);left=old['x'];top=old['y'];right=left+old['w'];bottom=top+old['h'];minimum=.025
        if kind=='move':self.crop.update(x=max(0,min(1-old['w'],left+p.x()-start.x())),y=max(0,min(1-old['h'],top+p.y()-start.y())))
        else:
            if 'l' in kind:left=min(p.x(),right-minimum)
            if 'r' in kind:right=max(p.x(),left+minimum)
            if 't' in kind:top=min(p.y(),bottom-minimum)
            if 'b' in kind:bottom=max(p.y(),top+minimum)
            self.crop.update(x=left,y=top,w=right-left,h=bottom-top)
        self.update()
    def mouseReleaseEvent(self,event):self.crop_drag=None;self.update()

class TrimTimeline(QWidget):
    changed=Signal(float,float)
    seek=Signal(float)
    def __init__(self,duration):
        super().__init__();self.duration=max(.1,duration);self.start=0.;self.end=duration;self.position=0.;self.thumbnails=[];self.drag=None;self.setMinimumHeight(92);self.setAccessibleName('Trim timeline: drag yellow handles to shorten video')
    def track(self):return QRectF(18,12,max(1,self.width()-36),58)
    def xpos(self,t):r=self.track();return r.left()+r.width()*t/self.duration
    def paintEvent(self,event):
        p=QPainter(self);r=self.track();p.fillRect(r,QColor('#34485f'))
        if self.thumbnails:
            width=r.width()/len(self.thumbnails)
            for i,image in enumerate(self.thumbnails):p.drawImage(QRectF(r.left()+width*i,r.top(),width+1,r.height()),image)
        else:
            p.setPen(QColor('#899db7'))
            for i in range(12):p.drawLine(QPointF(r.left()+r.width()*i/12,r.top()),QPointF(r.left()+r.width()*i/12,r.bottom()))
        a=self.xpos(self.start);b=self.xpos(self.end);p.fillRect(QRectF(r.left(),r.top(),a-r.left(),r.height()),QColor(0,0,0,180));p.fillRect(QRectF(b,r.top(),r.right()-b,r.height()),QColor(0,0,0,180));p.setPen(QPen(QColor('#ffdd00'),3));p.drawRect(QRectF(a,r.top(),b-a,r.height()))
        for x in [a,b]:p.fillRect(QRectF(x-7,r.top()-3,14,r.height()+6),QColor('#ffdd00'));p.setPen(QPen(QColor('#342e00'),2));p.drawLine(QPointF(x,r.top()+20),QPointF(x,r.bottom()-20))
        p.setPen(QPen(QColor('white'),2));x=self.xpos(self.position);p.drawLine(QPointF(x,r.top()-6),QPointF(x,r.bottom()+6));p.setPen(QColor('#cbd6e8'));p.drawText(QRectF(18,75,self.width()-36,17),f'{self.start:.2f}s     Selected: {self.end-self.start:.2f}s     {self.end:.2f}s')
    def mousePressEvent(self,event):
        x=event.position().x();a=self.xpos(self.start);b=self.xpos(self.end);self.drag='start' if abs(x-a)<18 else 'end' if abs(x-b)<18 else 'seek';self.mouseMoveEvent(event)
    def mouseMoveEvent(self,event):
        if not self.drag:return
        r=self.track();t=max(0,min(self.duration,(event.position().x()-r.left())/r.width()*self.duration));gap=min(.1,self.duration)
        if self.drag=='start':self.start=min(t,self.end-gap);self.changed.emit(self.start,self.end);self.seek.emit(self.start)
        elif self.drag=='end':self.end=max(t,self.start+gap);self.changed.emit(self.start,self.end);self.seek.emit(self.end)
        else:self.seek.emit(max(self.start,min(self.end,t)))
        self.update()
    def mouseReleaseEvent(self,event):self.drag=None

class CropDialog(QDialog):
    def __init__(self,main):
        super().__init__(main);self.setWindowTitle('Crop & trim · Simple Video Redactor');self.resize(960,760);self.boxes=[dict(b) for b in main.boxes];self.selected=-1;self.source=main.source;self.busy=False
        self.clean=QCheckBox();self.clean.setChecked(True);self.mode=QComboBox();self.mode.addItems(['keep','hide']);self.mode.setCurrentIndex(main.mode.currentIndex());self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.audio.setMuted(main.mute.isChecked());self.player.setAudioOutput(self.audio);self.sink=QVideoSink(self);self.player.setVideoSink(self.sink)
        root=QVBoxLayout(self);root.addWidget(QLabel('Drag any yellow corner to crop. Drag inside the crop frame to move it.'))
        self.screen=CropScreen(self);self.screen.image=main.screen.image.copy();self.sink.videoFrameChanged.connect(self.screen.frame);root.addWidget(self.screen,1)
        root.addWidget(QLabel('Drag the yellow timeline handles to remove footage from the beginning or end. Click the strip to scrub.'))
        self.timeline=TrimTimeline(main.player.duration()/1000);root.addWidget(self.timeline);self.timeline.seek.connect(lambda t:self.player.setPosition(int(t*1000)));self.timeline.changed.connect(self.range_changed)
        row=QHBoxLayout();self.play_button=QPushButton('▶ Play selection');self.play_button.clicked.connect(self.toggle);row.addWidget(self.play_button);self.start_time=QDoubleSpinBox();self.end_time=QDoubleSpinBox()
        for spin in [self.start_time,self.end_time]:spin.setDecimals(2);spin.setRange(0,self.timeline.duration);spin.valueChanged.connect(self.numeric_range)
        self.end_time.setValue(self.timeline.end);row.addWidget(QLabel('Start'));row.addWidget(self.start_time);row.addWidget(QLabel('End'));row.addWidget(self.end_time);root.addLayout(row)
        actions=QHBoxLayout();reset=QPushButton('Reset crop & trim');reset.clicked.connect(self.reset);actions.addWidget(reset);actions.addStretch();cancel=QPushButton('Cancel');cancel.clicked.connect(self.reject);actions.addWidget(cancel);apply=QPushButton('Apply & export…');apply.setObjectName('primary');apply.clicked.connect(self.apply);actions.addWidget(apply);root.addLayout(actions)
        self.player.positionChanged.connect(self.position);self.player.playbackStateChanged.connect(lambda s:self.play_button.setText('❚❚ Pause' if s==QMediaPlayer.PlaybackState.PlayingState else '▶ Play selection'));self.player.setSource(QUrl.fromLocalFile(str(main.preview)))
        self.player.mediaStatusChanged.connect(lambda s:self.player.setPosition(main.player.position()) if s==QMediaPlayer.MediaStatus.LoadedMedia else None)
        self.thumbs=QProcess(self);self.thumbs.finished.connect(self.load_thumbnails);self.thumb_dir=main.cache/next(tempfile._get_candidate_names());self.thumb_dir.mkdir()
        self.thumbs.start(engine(),['-y','-i',str(main.preview),'-vf',f'fps={10/max(.1,self.timeline.duration)},scale=120:-1','-frames:v','10',str(self.thumb_dir/'frame-%02d.png')])
    def load_thumbnails(self,*args):
        self.timeline.thumbnails=[QImage(str(p)) for p in sorted(self.thumb_dir.glob('frame-*.png'))];self.timeline.update()
    def range_changed(self,start,end):
        for spin,value in [(self.start_time,start),(self.end_time,end)]:spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
    def numeric_range(self):
        a=self.start_time.value();b=self.end_time.value()
        if b>a:self.timeline.start=a;self.timeline.end=b;self.timeline.update()
    def toggle(self):
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause()
        else:
            if not self.timeline.start<=self.player.position()/1000<self.timeline.end:self.player.setPosition(int(self.timeline.start*1000))
            self.player.play()
    def position(self,ms):
        self.timeline.position=ms/1000;self.timeline.update();self.screen.update()
        if ms/1000>=self.timeline.end and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause();self.player.setPosition(int(self.timeline.start*1000))
    def reset(self):self.screen.crop=dict(x=0.,y=0.,w=1.,h=1.);self.screen.update();self.timeline.start=0.;self.timeline.end=self.timeline.duration;self.timeline.update();self.range_changed(0,self.timeline.duration)
    def apply(self):
        if self.end_time.value()<=self.start_time.value():QMessageBox.warning(self,'Trim times','End must be later than start.');return
        self.numeric_range();self.accept()
    def shutdown(self):
        self.player.stop();self.player.setSource(QUrl());self.thumbs.kill();self.thumbs.waitForFinished(1000);shutil.rmtree(self.thumb_dir,ignore_errors=True)

class BoxListDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(280,68)
    def paint(self,painter,option,index):
        painter.save();selected=bool(option.state & QStyle.StateFlag.State_Selected);hover=bool(option.state & QStyle.StateFlag.State_MouseOver)
        r=QRectF(option.rect).adjusted(2,2,-2,-2)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#72dfb6' if selected else '#40536a' if hover else '#2d3d52'),1))
        painter.setBrush(QColor('#203e3a' if selected else '#26364a' if hover else '#1c293a'));painter.drawRoundedRect(r,9,9)
        number,tracked,start,end=index.data(Qt.ItemDataRole.UserRole)
        badge=QRectF(r.left()+12,r.top()+15,34,34);painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#72dfb6' if selected else '#33465c'));painter.drawRoundedRect(badge,8,8)
        font=option.font;font.setBold(True);painter.setFont(font);painter.setPen(QColor('#122c26' if selected else '#e9eef8'));painter.drawText(badge,Qt.AlignmentFlag.AlignCenter,str(number))
        title=QRectF(r.left()+58,r.top()+9,r.width()-70,24);painter.setPen(QColor('#f0f6fc'));painter.drawText(title,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f'Box {number}')
        font.setBold(False);font.setPointSize(9);painter.setFont(font);painter.setPen(QColor('#9eb2c9'));painter.drawText(QRectF(r.left()+58,r.top()+34,r.width()-70,21),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f'{start:.2f}s – {end:.2f}s')
        status='TRACKED' if tracked else 'FIXED';width=70 if tracked else 54;tag=QRectF(r.right()-width-12,r.top()+12,width,22)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#284d43' if tracked else '#304054'));painter.drawRoundedRect(tag,5,5);painter.setPen(QColor('#8ae6bd' if tracked else '#bac9da'));font.setPointSize(8);font.setBold(True);painter.setFont(font);painter.drawText(tag,Qt.AlignmentFlag.AlignCenter,status)
        painter.restore()

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('Simple Video Redactor');self.resize(1160,900)
        self.cache=pathlib.Path(tempfile.mkdtemp(prefix='VideoRedactor-'));self.source=None;self.boxes=[];self.selected=-1;self.busy=False;self.operation='';self.job=None;self.preview=self.cache/'preview.mp4';self.output=None;self.temp_output=None
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio);self.sink=QVideoSink(self);self.player.setVideoSink(self.sink)
        self.process=QProcess(self);self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels);self.log=b'';self.process.readyReadStandardOutput.connect(self.read_log);self.process.finished.connect(self.finished);self.process.errorOccurred.connect(self.process_error)
        central=QWidget();self.setCentralWidget(central);root=QVBoxLayout(central);root.setContentsMargins(24,20,24,20)
        title=QLabel('Simple Video Redactor');title.setStyleSheet('font-size:26px;font-weight:700');heading=QHBoxLayout();heading.addWidget(title,1);coffee=QPushButton('☕ Buy me a coffee');coffee.setToolTip('If this software helped you');coffee.setStyleSheet('background:#ffdd00;color:#1c1c1c;font-weight:700');coffee.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://buymeacoffee.com/bigzz')));heading.addWidget(coffee);root.addLayout(heading);root.addWidget(QLabel('All video processing stays on this computer'))
        top=QHBoxLayout();self.import_button=QPushButton('Import video…');self.import_button.clicked.connect(self.import_video);self.name=QLabel('MP4, AVI, MOV, MKV and more');top.addWidget(self.import_button);top.addWidget(self.name,1);root.addLayout(top)
        body=QHBoxLayout();root.addLayout(body,1);left=QVBoxLayout();body.addLayout(left,1);right=QVBoxLayout();body.addLayout(right);self.screen=Screen(self);self.sink.videoFrameChanged.connect(self.screen.frame);self.screen.changed.connect(self.refresh);left.addWidget(self.screen,1)
        playback=QHBoxLayout();self.play=QPushButton('▶ Play');self.play.clicked.connect(self.toggle_play);playback.addWidget(self.play);back=QPushButton('−1 sec');back.clicked.connect(lambda:self.player.setPosition(max(0,self.player.position()-1000)));playback.addWidget(back);self.time=QLabel('00:00 / 00:00');playback.addWidget(self.time);self.clean=QCheckBox('Clean redaction preview');self.clean.setChecked(True);self.clean.toggled.connect(self.screen.update);playback.addWidget(self.clean);left.addLayout(playback)
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.sliderMoved.connect(self.player.setPosition);left.addWidget(self.seek)
        hint=QLabel('Pause and drag to draw. Select a box to move it; drag its bottom-right corner to resize.');hint.setWordWrap(True);left.addWidget(hint)
        right.addWidget(QLabel('Redaction method'));self.mode=QComboBox();self.mode.addItems(['Keep boxes visible · black out outside','Hide boxes · black out inside']);self.mode.currentIndexChanged.connect(self.screen.update);right.addWidget(self.mode)
        self.draw_button=QPushButton('+ Draw another box');self.draw_button.clicked.connect(self.new_box);right.addWidget(self.draw_button);self.box_heading=QLabel("Subjects · 0 boxes");right.addWidget(self.box_heading);self.box_list=QListWidget();self.box_list.setMinimumWidth(300);self.box_list.setMinimumHeight(170);self.box_list.setMouseTracking(True);self.box_list.setSpacing(4);self.box_list.setItemDelegate(BoxListDelegate(self.box_list));self.box_list.currentRowChanged.connect(self.select_box);right.addWidget(self.box_list,1)
        self.track_button=QPushButton('Track selected subject');self.track_button.clicked.connect(self.track_selected);right.addWidget(self.track_button)
        self.untrack_button=QPushButton('Make selected box fixed');self.untrack_button.clicked.connect(self.untrack);right.addWidget(self.untrack_button)
        self.cancel_button=QPushButton('Cancel tracking / mask');self.cancel_button.clicked.connect(self.cancel_job);self.cancel_button.setVisible(False);right.addWidget(self.cancel_button)
        right.addWidget(QLabel('Selected box times (seconds)'));times=QHBoxLayout();self.start=QDoubleSpinBox();self.end=QDoubleSpinBox()
        for spin in [self.start,self.end]:spin.setDecimals(2);spin.setRange(0,999999);spin.valueChanged.connect(self.change_times)
        times.addWidget(QLabel('From'));times.addWidget(self.start);times.addWidget(QLabel('To'));times.addWidget(self.end);right.addLayout(times)
        delete=QPushButton('Delete selected box');delete.clicked.connect(self.delete_box);right.addWidget(delete);clear=QPushButton('Clear all boxes');clear.clicked.connect(self.clear);right.addWidget(clear)
        self.mute=QCheckBox('Remove audio from export');right.addWidget(self.mute);note=QLabel('Draw around a subject, then click Track selected subject. Tracking can drift: review the whole video, adjust the box and retrack if needed.');note.setWordWrap(True);note.setMaximumWidth(320);right.addWidget(note)
        self.export_button=QPushButton('Export redacted MP4…');self.export_button.setObjectName('primary');self.export_button.clicked.connect(self.export);right.addWidget(self.export_button)
        self.status=QLabel('Ready to import.');self.status.setWordWrap(True);root.addWidget(self.status)
        self.player.positionChanged.connect(self.position);self.player.durationChanged.connect(self.duration);self.player.playbackStateChanged.connect(lambda s:self.play.setText('❚❚ Pause' if s==QMediaPlayer.PlaybackState.PlayingState else '▶ Play'));self.player.errorOccurred.connect(lambda e,s:self.status.setText('Playback error: '+s));self.refresh()
    def duration(self,d):self.seek.setRange(0,d);self.position(self.player.position())
    def position(self,pos):
        if not self.seek.isSliderDown():self.seek.setValue(pos)
        def t(ms):return f'{ms//60000:02d}:{ms//1000%60:02d}'
        self.time.setText(t(pos)+' / '+t(self.player.duration()));self.screen.update()
    def toggle_play(self):
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause()
        else:self.clean.setChecked(True);self.screen.draw=False;self.player.play()
    def refresh(self):
        self.box_list.blockSignals(True);self.box_list.clear();self.box_heading.setText(f'Subjects · {len(self.boxes)} '+('box' if len(self.boxes)==1 else 'boxes'));
        for i,b in enumerate(self.boxes):
            item=QListWidgetItem(f'Box {i+1} · '+('tracked' if b.get('track') else 'fixed')+f" · {b['start']:.2f}s to {b['end']:.2f}s");item.setData(Qt.ItemDataRole.UserRole,(i+1,bool(b.get('track')),b['start'],b['end']));self.box_list.addItem(item)
        self.box_list.setCurrentRow(self.selected);self.box_list.blockSignals(False);self.select_box(self.selected)
        self.import_button.setEnabled(not self.busy);self.export_button.setEnabled(bool(self.source and self.boxes) and not self.busy);self.draw_button.setEnabled(bool(self.source) and not self.busy);self.play.setEnabled(bool(self.source) and not self.busy);self.mode.setEnabled(not self.busy)
    def select_box(self,i):
        self.selected=i
        for spin in [self.start,self.end]:spin.blockSignals(True);spin.setEnabled(0<=i<len(self.boxes) and not self.busy)
        if 0<=i<len(self.boxes):
            self.start.setValue(self.boxes[i]['start']);self.end.setValue(self.boxes[i]['end']);self.screen.draw=False
        for spin in [self.start,self.end]:spin.blockSignals(False)
        self.track_button.setEnabled(0<=i<len(self.boxes) and not self.busy);self.untrack_button.setEnabled(0<=i<len(self.boxes) and bool(self.boxes[i].get('track')) and not self.busy)
        self.screen.update()
    def change_times(self):
        if 0<=self.selected<len(self.boxes):self.boxes[self.selected].pop('track',None);self.boxes[self.selected].update(start=self.start.value(),end=self.end.value());self.refresh();self.screen.update()
    def start_job(self,task,completed,label):
        self.busy=True;self.refresh();self.cancel_button.setVisible(True)
        self.job=BackgroundJob(task,self);self.job.progress.connect(lambda n:self.status.setText(f'{label} {n}%'))
        self.job.result.connect(completed);self.job.failed.connect(self.job_failed);self.job.start()
    def job_done(self):
        self.busy=False;self.cancel_button.setVisible(False);self.refresh()
    def job_failed(self,message):
        self.job_done();self.status.setText(message)
        if 'cancelled' not in message.lower():QMessageBox.warning(self,'Tracking / export',message)
    def cancel_job(self):
        if self.job and self.job.isRunning():self.job.requestInterruption();self.status.setText('Cancelling…')
    def track_selected(self):
        if self.busy or not 0<=self.selected<len(self.boxes):return
        self.player.pause();index=self.selected;seed=self.player.position()/1000;box=dict(box_at(self.boxes[index],seed));box.pop('track',None)
        if not box['start']<=seed<=box['end']:
            QMessageBox.warning(self,'Choose a frame','Seek to a frame within the selected box time range.');return
        def complete(samples):
            self.boxes[index]['track']=samples;self.job_done();self.screen.draw=False;self.status.setText('Tracking complete. Play or scrub to review. To correct: pause, move/resize the box, then track again.');self.screen.update()
        self.start_job(lambda progress,cancel:track_subject(self.preview,box,seed,progress,cancel),complete,'Tracking subject…')
    def untrack(self):
        if self.busy or not 0<=self.selected<len(self.boxes):return
        box=self.boxes[self.selected];current=box_at(box,self.player.position()/1000);box.update({k:current[k] for k in ('x','y','w','h')});box.pop('track',None);self.refresh();self.screen.update()
    def new_box(self):self.player.pause();self.screen.draw=True;self.clean.setChecked(False);self.selected=-1;self.refresh();self.status.setText('Drag on the video to draw a box.')
    def delete_box(self):
        if self.busy:return
        if 0<=self.selected<len(self.boxes):self.boxes.pop(self.selected)
        self.selected=-1;self.refresh()
    def clear(self):
        if self.busy:return
        self.boxes=[];self.selected=-1;self.screen.draw=True;self.refresh()
    def run(self,command,operation):
        self.busy=True;self.operation=operation;self.log=b'';self.import_dimensions=None;self.refresh();self.status.setText('Preparing video for preview…' if operation=='import' else 'Rendering redacted MP4…');self.process.start(command[0],command[1:])
    def read_log(self):
        self.log=(self.log+bytes(self.process.readAllStandardOutput()))[-12000:]
        if self.operation=='import' and not self.import_dimensions:
            match=re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b',self.log.decode(errors='replace'))
            if match:self.import_dimensions=tuple(map(int,match.groups()))
    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:self.busy=False;self.refresh();QMessageBox.critical(self,'Video engine error',self.process.errorString())
    def finished(self,code,state):
        self.read_log();self.busy=False
        if code!=0:
            if self.operation=='import':self.source=None;self.boxes=[];self.selected=-1
            self.status.setText('Processing failed.');QMessageBox.critical(self,'Processing failed',self.log.decode(errors='replace')[-2500:]);self.refresh();return
        if self.operation=='import':
            if self.import_dimensions:self.width,self.height=self.import_dimensions
            else:self.source=None;QMessageBox.critical(self,'Import failed','Could not read video dimensions.');self.refresh();return
            self.boxes=[];self.selected=-1;self.screen.draw=True;self.clean.setChecked(False);self.need_first=True;self.player.setSource(QUrl.fromLocalFile(str(self.preview)));self.player.play();self.status.setText('Ready. Draw boxes around the areas you want to KEEP visible.')
        else:
            try:
                self.temp_output.replace(self.output)
            except OSError as e:QMessageBox.critical(self,'Could not save export',str(e));self.refresh();return
            self.status.setText('Export saved: '+str(self.output));answer=QMessageBox.question(self,'Export complete','Redacted video saved. Open it now to review?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if answer==QMessageBox.StandardButton.Yes:
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output)))
        self.refresh()
    def import_video(self):
        name,_=QFileDialog.getOpenFileName(self,'Import video',str(pathlib.Path.home()/'Downloads'),'Videos (*.mp4 *.avi *.mov *.mkv *.wmv *.webm *.m4v *.mpg *.mpeg *.mts *.m2ts *.ts *.3gp *.flv *.vob *.ogv *.asf);;All files (*)')
        if not name:return
        self.load(name)
    def load(self,name):
        self.player.stop();self.player.setSource(QUrl());self.screen.image=QImage();self.screen.update();self.source=pathlib.Path(name);self.name.setText(self.source.name)
        cmd=[engine(),'-y','-noautorotate','-i',str(self.source),'-map','0:v:0','-map','0:a:0?','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-metadata:s:v:0','rotate=0','-movflags','+faststart',str(self.preview)]
        self.run(cmd,'import')
    def export(self):
        if not self.boxes or self.busy:return
        if any(b['end']<b['start'] for b in self.boxes):QMessageBox.warning(self,'Box times','Each box must end after it starts.');return
        self.player.pause();crop=None;trim=None
        answer=QMessageBox.question(self,'Crop before export?','Would you like to crop this video before you export?\n\nYou can also shorten it using the trim handles.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Cancel:return
        if answer==QMessageBox.StandardButton.Yes:
            dialog=CropDialog(self)
            result=dialog.exec();dialog.shutdown()
            if result!=QDialog.DialogCode.Accepted:return
            crop=dict(dialog.screen.crop);trim=(dialog.timeline.start,dialog.timeline.end)
        name,_=QFileDialog.getSaveFileName(self,'Save redacted video',str(self.source.with_name(self.source.stem+'_redacted.mp4')),'MP4 video (*.mp4)')
        if not name:return
        output=pathlib.Path(name)
        if output.suffix.lower()!='.mp4':output=output.with_suffix('.mp4')
        if output.resolve()==self.source.resolve():QMessageBox.warning(self,'Choose a different file','Choose a new filename to preserve the original.');return
        self.output=output;self.temp_output=output.with_name(output.stem+'.rendering-'+next(tempfile._get_candidate_names())+'.mp4');self.player.pause()
        boxes=[dict(b) for b in self.boxes];mode='keep' if self.mode.currentIndex()==0 else 'hide'
        if any(b.get('track') for b in boxes):
            mask=self.cache/'tracking-mask.mkv'
            def complete(_):
                self.job_done();self.run(export_command(self.source,self.temp_output,boxes,mode,self.mute.isChecked(),self.width,self.height,crop,trim,mask),'export')
            self.start_job(lambda progress,cancel:render_mask(engine(),self.preview,mask,boxes,mode,self.width,self.height,progress,cancel),complete,'Preparing moving redactions…')
        else:self.run(export_command(self.source,self.temp_output,boxes,mode,self.mute.isChecked(),self.width,self.height,crop,trim),'export')
    def closeEvent(self,event):
        if self.busy:
            answer=QMessageBox.question(self,'Processing in progress','Cancel processing and close?')
            if answer!=QMessageBox.StandardButton.Yes:event.ignore();return
            if self.job and self.job.isRunning():
                self.job.requestInterruption();self.job.wait()
            self.process.kill();self.process.waitForFinished(3000)
        self.player.stop();self.player.setSource(QUrl())
        if self.temp_output and self.temp_output.exists():self.temp_output.unlink(missing_ok=True)
        shutil.rmtree(self.cache,ignore_errors=True);event.accept()

STYLE='''QWidget{background:#141c28;color:#e9eef8;font:14px "Segoe UI";} QPushButton,QComboBox,QDoubleSpinBox{background:#26354a;border:1px solid #40506a;border-radius:6px;padding:9px;} QPushButton:hover{background:#34485f;} QPushButton:disabled{color:#6e7a8b;} QPushButton#primary{background:#72dfb6;color:#14281f;font-weight:700;} QListWidget{background:#1b2636;border:1px solid #40506a;border-radius:6px;} QListWidget{padding:5px;} QListWidget::item{padding:0px;} QSlider::groove:horizontal{height:6px;background:#35465d;} QSlider::handle:horizontal{background:#72dfb6;width:14px;margin:-5px 0;border-radius:7px;}'''
if __name__=='__main__':
    app=QApplication(sys.argv);app.setApplicationName('Simple Video Redactor');app.setStyleSheet(STYLE);window=Window();window.show()
    sys.exit(app.exec())
