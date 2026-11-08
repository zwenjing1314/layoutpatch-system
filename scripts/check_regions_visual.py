"""Deterministic first-type coordinate overlays, distinct from genuine browser screenshots."""
import json
import sqlite3
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from backend.db.connection import ROOT
from scripts.check_regions import OUT,STATE,read
from scripts.check_regions_http import save


def main():
    chosen={};state=read(STATE);target=ROOT/'docs/checks/stage2-6-coordinate-images';target.mkdir(exist_ok=False)
    with sqlite3.connect(f'file:{(OUT/"metadata.sqlite3").as_posix()}?mode=ro',uri=True) as db:
        for spec in state['selected']:
            rows=db.execute('select p.id,p.page_index,p.image_path,pp.candidates_json from pages p join page_parses pp on pp.page_id=p.id where p.document_version_id=? and pp.task_id=? order by p.page_index',(spec['document_version_id'],spec['task_id'])).fetchall()
            for page_id,index,path,encoded in rows:
                for c in json.loads(encoded):
                    if c['type'] not in ('image','table','text','equation') or c['type'] in chosen:continue
                    chosen[c['type']]={'owner':spec['owner'],'page_number':index+1,'page_id':page_id,'source_image':path,'candidate':c}
    assert set(chosen)=={'image','table','text','equation'}
    sheet=Image.new('RGB',(840,1180),'#edf2ef');draw=ImageDraw.Draw(sheet)
    for n,kind in enumerate(('image','table','text','equation')):
        c=chosen[kind];image=Image.open(ROOT/c['source_image']).convert('RGB');d=ImageDraw.Draw(image)
        d.rectangle(c['candidate']['bbox'],outline='#ef6c00',width=5)
        name=f"{kind}-{c['owner']}-page{c['page_number']}-id{c['candidate']['layout_id']}.png";image.save(target/name)
        c['overlay']=(target/name).relative_to(ROOT).as_posix()
        thumb=ImageOps.contain(image,(410,545));x=(n%2)*420;y=(n//2)*590;sheet.paste(thumb,(x,y+35));draw.text((x+8,y+8),f"{kind}: {c['owner']} page {c['page_number']} / id {c['candidate']['layout_id']}",fill='#172b23')
    sheet.save(target/'contact.png')
    save(ROOT/'docs/checks/stage2-6-visual.json',{'round':'R22','overall':'generated_pending_visual_review','selection':'First candidate of each type by owner A/B, page_index and layout order; no gold or quality selection','examples':chosen,'limits':'Generated server-coordinate overlays for visual QA, not browser screenshots or detector accuracy. Browser screenshots kept separately.'})
    print('Generated four deterministic full-size coordinate examples and contact sheet')


if __name__=='__main__':main()
