from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import argparse, json, glob
W,H=2480,1860
im=Image.new('L',(W,H),250); d=ImageDraw.Draw(im)
ink,muted,rule,card=30,105,205,238
jp=next(iter(glob.glob(str(Path.home() / '.cache/scribe-fonts/NotoSansCJK-Regular.ttc')) + glob.glob('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc') + glob.glob('/System/Library/Fonts/*角*W3.ttc')), None)
if not jp: raise RuntimeError('Japanese font missing: install fonts-noto-cjk')
reg=next(p for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/System/Library/Fonts/Supplemental/Arial.ttf'] if Path(p).exists())
bold=next(p for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf'] if Path(p).exists())
serif=next(p for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf','/System/Library/Fonts/Supplemental/Georgia.ttf'] if Path(p).exists())
def f(n,kind='r'): return ImageFont.truetype({'r':reg,'b':bold,'s':serif,'j':jp}[kind],n)
def text(pos,s,n=42,kind='r',color=ink): d.text(pos,s,font=f(n,kind),fill=color)
def fit(pos, value, size, max_width, kind='r', color=ink):
 while size > 22 and d.textlength(str(value), font=f(size, kind)) > max_width: size -= 2
 text(pos, str(value), size, kind, color)
def line(y,x1=105,x2=1370): d.line((x1,y,x2,y),fill=rule,width=3)
parser=argparse.ArgumentParser()
parser.add_argument('--data',default='demo.json')
parser.add_argument('--output',default='site/dashboard.png')
parser.add_argument('--state', default=None)
args=parser.parse_args()
data=json.loads(Path(args.data).read_text(encoding='utf-8'))
now=datetime.now(ZoneInfo('Asia/Tokyo'))
text((105,90),now.strftime('%A, %B %-d'),76,'s')

text((105,250),"TODAY'S AGENDA",42,'b'); text((108,318),data.get('events_status','SAMPLE EVENTS'),28,'b',muted); line(380)
for i,(time,title) in enumerate([(e['time'],e['title']) for e in data['events'][:4]]):
 y=410+i*175; text((110,y),time,48,'b',muted); fit((340,y-2),title,60,1020,'j'); line(y+130)
# right weather panel
x=1450; right=2375

d.rounded_rectangle((x,90,right,710),radius=25,fill=card)
fit((x+48,123),data['weather']['display_temperature'],112,830,'b'); text((x+51,255),data['weather']['condition'],61)
fit((x+52,339),data['weather']['high_low'],39,830,color=muted)
d.line((x+50,415,right-50,415),fill=rule,width=2)
for i,(t,temp,rain) in enumerate([(v['time'],v['temperature'],v['precipitation']) for v in data['weather']['forecast'][:5]]):
 xx=x+50+i*166; text((xx,448),t,29,'b',muted); text((xx,505),temp,32,'b'); text((xx,581),rain,34,color=muted)
text((x+50,655),data['weather'].get('status','SAMPLE  ·  PRECIPITATION CHANCE').upper(),24,'b',muted)
# Japanese practice card

d.rounded_rectangle((x,830,right,1452),radius=25,outline=rule,width=3)
text((x+48,860),data['kanji']['character'],210,'j'); fit((x+335,917),data['kanji']['meaning'],52,530,'b'); fit((x+337,1000),data['kanji']['readings'],38,530,'j',muted)
d.line((x+50,1150,right-50,1150),fill=rule,width=2)
for i,(word,reading,meaning) in enumerate([(v['word'],v['reading'],v['meaning']) for v in data['kanji']['examples'][:3]]):
 y=1185+i*70; text((x+52,y),word,42,'j'); fit((x+235,y+6),reading,33,255,'j',muted); fit((x+505,y+6),meaning,34,355)
text((105,1170),'SHARED TASKS',42,'b'); text((108,1235),data.get('tasks_status', 'SAMPLE  ·  NOTION'),28,'b',muted); line(1285)
for i,title in enumerate(data['tasks'][:5]):
 y=1315+i*78; d.rounded_rectangle((110,y+9,145,y+44),radius=4,outline=muted,width=3); fit((175,y),title,40,1180,'j')
d.line((105,1750,2375,1750),fill=ink,width=3)
text((105,1780),'WEATHER: OPEN-METEO  ·  DICTIONARY: EDRDG / KANJIAPI.DEV',27,'b',muted)
stamp='Generated at '+now.strftime('%Y-%m-%d %H:%M JST'); box=d.textbbox((0,0),stamp,font=f(30)); text((2375-box[2],1778),stamp,30,color=muted)
# Draw in landscape; rotate only the final image for the Scribe.
output=Path(args.output)
output.parent.mkdir(parents=True,exist_ok=True)
pnginfo = PngImagePlugin.PngInfo()
if args.state:
 pnginfo.add_text('scribe_widget_state_v1', Path(args.state).read_text(encoding='utf-8'))
im.transpose(Image.Transpose.ROTATE_270).save(output,optimize=True,pnginfo=pnginfo)
