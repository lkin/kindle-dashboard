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
def wrapped(pos, value, size, width, max_lines=3):
 value = str(value).strip()
 def split(font):
  lines = []
  for word in value.split():
   if lines and d.textlength(lines[-1] + ' ' + word, font=font) <= width:
    lines[-1] += ' ' + word
   else:
    while word and d.textlength(word, font=font) > width:
     n = len(word)
     while n > 1 and d.textlength(word[:n], font=font) > width: n -= 1
     lines.append(word[:n]); word = word[n:]
    if word: lines.append(word)
  return lines
 while size > 24:
  font = f(size)
  lines = split(font)
  if len(lines) <= max_lines: break
  size -= 2
 font = f(size); lines = split(font)
 if len(lines) > max_lines:
  lines = lines[:max_lines]
  while lines[-1] and d.textlength(lines[-1] + '…', font=font) > width: lines[-1] = lines[-1][:-1]
  lines[-1] += '…'
 for i, value in enumerate(lines): d.text((pos[0],pos[1]+i*(size+5)),value,font=font,fill=ink)
def line(y,x1=105,x2=1370): d.line((x1,y,x2,y),fill=rule,width=3)
parser=argparse.ArgumentParser()
parser.add_argument('--data',default='demo.json')
parser.add_argument('--output',default='site/dashboard.png')
parser.add_argument('--state', default=None)
args=parser.parse_args()
data=json.loads(Path(args.data).read_text(encoding='utf-8'))
now=datetime.now(ZoneInfo('Asia/Tokyo'))
text((105,90),now.strftime('%A, %B %-d'),76,'s')
koyomi = data.get('koyomi')
if koyomi:
 fields = [koyomi.get(key, '') for key in ('inreki','eto','sekki','rokuyou','holiday')]
 fit((105,190),'  ·  '.join(value for value in fields if value),42,1265,'j')

text((105,280),"TODAY'S AGENDA",42,'b')
if data.get('events_status') in ('CALENDAR UNAVAILABLE', 'CALENDAR SETUP REQUIRED', 'NO EVENTS TODAY'):
 text((108,340),data['events_status'],28,'b',muted)
for i,(time,title) in enumerate([(e['time'],e['title']) for e in data['events'][:4]]):
 y=410+i*175; text((110,y),time,48,'b',muted); fit((340,y-2),title,60,1020,'j'); line(y+130)
# right weather panel
x=1450; right=2375

d.rounded_rectangle((x,90,right,710),radius=25,fill=card)
fit((x+48,123),data['weather']['display_temperature'],112,830,'b'); text((x+51,255),data['weather']['condition'],61)
fit((x+52,339),data['weather']['high_low'],39,830)
d.line((x+50,415,right-50,415),fill=rule,width=2)
for i,(t,temp,rain) in enumerate([(v['time'],v['temperature'],v['precipitation']) for v in data['weather']['forecast'][:5]]):
 xx=x+50+i*166; text((xx,448),t,29,'b',muted); text((xx,505),temp,32,'b'); text((xx,581),rain,34)
weather_status = data['weather'].get('status','')
if weather_status and weather_status.lower() not in ('precipitation chance', 'sample  ·  precipitation chance'):
 text((x+50,655),weather_status.upper(),24,'b',muted)
# Japanese practice card

d.rounded_rectangle((x,830,right,1705),radius=25,outline=rule,width=3)
text((x+48,860),data['kanji']['character'],210,'j'); fit((x+335,910),data['kanji']['meaning'],62,530,'b'); fit((x+337,1005),data['kanji']['readings'],47,530,'j',muted)
d.line((x+50,1150,right-50,1150),fill=rule,width=2)
for i,(word,reading,meaning) in enumerate([(v['word'],v['reading'],v['meaning']) for v in data['kanji']['examples'][:3]]):
 y=1180+i*160; fit((x+52,y),word,48,170,'j'); fit((x+235,y+8),reading,39,255,'j',muted); wrapped((x+505,y+5),meaning,38,355)
text((105,1170),'PENDING TASKS',42,'b')
if data.get('tasks_status') in ('NOTION UNAVAILABLE', 'NO OPEN TASKS'):
 text((108,1235),data['tasks_status'],28,'b',muted)
for i,title in enumerate(data['tasks'][:5]):
 y=1315+i*78; d.rounded_rectangle((110,y+9,145,y+44),radius=4,outline=muted,width=3); fit((175,y),title,40,1180,'j')
d.line((105,1750,2375,1750),fill=ink,width=3)
text((105,1780),'WEATHER: OPEN-METEO  ·  DICTIONARY: EDRDG / KANJIAPI.DEV  ·  TASKS: NOTION  ·  CALENDAR: GOOGLE',23,'b',muted)
stamp='GENERATED AT '+now.strftime('%Y-%m-%d %H:%M JST'); box=d.textbbox((0,0),stamp,font=f(23,'b')); text((2375-box[2],1780),stamp,23,'b',muted)
# Draw in landscape; rotate only the final image for the Scribe.
output=Path(args.output)
output.parent.mkdir(parents=True,exist_ok=True)
pnginfo = PngImagePlugin.PngInfo()
if args.state:
 pnginfo.add_text('scribe_widget_state_v1', Path(args.state).read_text(encoding='utf-8'))
im.transpose(Image.Transpose.ROTATE_270).save(output,optimize=True,pnginfo=pnginfo)
