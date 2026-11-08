"""Verify ALL real candidates/provenance and render inspection overlays from their actual boxes."""
from collections import Counter
import json
import math

from PIL import Image,ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT,make_engine
from backend.db.models import Document,DocumentVersion,Page,PageParse,ParserProfile,ParsingTask,User
from backend.db.seed import canonical,sha
from backend.parsing.adapter import digest,load_profile
from backend.parsing.candidates import export_candidates,finite_box
from backend.parsing.store import read_candidates
from scripts.check_parsing import OUT,STATE,DATABASE,read,write


def main():
    state=read(STATE);engine=make_engine(DATABASE)
    overlay_dir=OUT/'overlays';overlay_dir.mkdir(exist_ok=False)
    checks=[];pages=[];types=Counter();thumbs=[];total_forwards=0
    def check(name,condition,**detail):
        checks.append({'name':name,'passed':bool(condition),**detail})
        if not condition:raise AssertionError(name)
    colors={'text':'#1655BB','title':'#8E27AE','image':'#07823E','table':'#D62030','equation':'#A75B00'}
    with Session(engine) as db:
        for selected in state['selected']:
            task=db.scalar(select(ParsingTask).where(ParsingTask.document_version_id==selected['version_id']).order_by(ParsingTask.created_at.desc()).limit(1))
            profile=db.get(ParserProfile,task.parser_profile_id);version=db.get(DocumentVersion,task.document_version_id)
            user=db.scalar(select(User).where(User.username==selected['owner']))
            check(selected['owner']+'_current_profile_real_complete',task.status=='ready' and profile.config_json==canonical(load_profile()))
            check(selected['owner']+'_source_pdf_identity',digest(ROOT/version.pdf_path)==version.pdf_sha256==selected['pdf_sha256'])
            rows=db.execute(select(PageParse,Page).join(Page,Page.id==PageParse.page_id).where(PageParse.task_id==task.id).order_by(Page.page_index)).all()
            check(selected['owner']+'_complete_source_page_sequence',[p.page_index for _,p in rows]==list(range(selected['pages'])))
            for record,page in rows:
                name=selected['owner']+f'_p{page.page_index+1}'
                candidates,identity=read_candidates(db,user,page.id,task.id)
                provenance=json.loads(record.provenance_json)
                output=ROOT/'runtime/parsing'/task.id/page.id
                receipt=read(output/'receipt.json');raw=read(output/'raw.json')
                check(name+'_raw_receipt_source_hashes',digest(output/'raw.json')==provenance['raw_sha256']==receipt['raw_sha256'] and digest(output/'receipt.json')==provenance['receipt_sha256'] and provenance['pdf_sha256']==version.pdf_sha256)
                check(name+'_actual_cpu_forward_no_network_or_write_escape',receipt['status']=='completed' and receipt['network_attempts']==0 and receipt['blocked_writes']==0 and all(s['providers']==['CPUExecutionProvider'] for s in receipt['sessions']) and sum(s['forward_calls'] for s in receipt['sessions'])>0)
                total_forwards+=sum(s['forward_calls'] for s in receipt['sessions'])
                check(name+'_same_png_and_geometry',digest(ROOT/page.image_path)==page.render_sha256==provenance['geometry']['render_sha256'])
                expected=export_candidates(raw,{k:candidates[0][k] for k in ('document_id','document_version_id','page_id','page_index','page_number','width_px','height_px','render_sha256','parser_profile_sha256')},provenance['geometry'])
                check(name+'_exact_raw_reexport_and_finite_boxes',expected==candidates and all(finite_box(c['bbox'],[page.width_px,page.height_px]) for c in candidates))
                check(name+'_candidate_ids_unique_and_typed',len({c['candidate_id'] for c in candidates})==len(candidates) and all(c['type'] in colors for c in candidates))
                types.update(c['type'] for c in candidates)
                with Image.open(ROOT/page.image_path) as original:image=original.copy()
                draw=ImageDraw.Draw(image)
                for c in candidates:
                    box=c['bbox'];color=colors[c['type']]
                    draw.rectangle(box,outline=color,width=3)
                    label=f"{c['layout_id']}:{c['type']}"
                    draw.text((box[0]+2,box[1]+2),label,fill=color,stroke_width=1,stroke_fill='white')
                overlay=overlay_dir/(name+'.png');image.save(overlay)
                if name in {'A_p2','A_p4','B_p5'}:
                    target=ROOT/'docs/checks'/('stage2-4-'+name+'-overlay.png')
                    if target.exists():raise RuntimeError('Overlay exists; preserve prior evidence')
                    target.write_bytes(overlay.read_bytes())
                image.thumbnail((420,570))
                thumb=Image.new('RGB',(440,610),'#F4F5F7');thumb.paste(image,((440-image.width)//2,30))
                ImageDraw.Draw(thumb).text((10,8),f'{name}: {len(candidates)} candidates / PNG {page.width_px}x{page.height_px}',fill='black')
                thumbs.append(thumb)
                pages.append({'owner':selected['owner'],'task_id':task.id,'page_id':page.id,'page_index':page.page_index,'candidate_count':len(candidates),'types':dict(Counter(c['type'] for c in candidates)),'candidate_hash':record.candidate_hash,'profile_sha256':profile.config_sha256,'render_sha256':page.render_sha256,'overlay':overlay.relative_to(ROOT).as_posix(),'seconds':receipt['seconds']})
    engine.dispose()
    sheet=Image.new('RGB',(440*3,610*math.ceil(len(thumbs)/3)),'white')
    for i,thumb in enumerate(thumbs):sheet.paste(thumb,((i%3)*440,(i//3)*610))
    sheet.save(overlay_dir/'contact.png')
    write(ROOT/'docs/checks/stage2-4-output.json',{'round':'R20','overall':'passed','checks':checks,'pages':pages,'candidate_count':sum(p['candidate_count'] for p in pages),'types':dict(types),'actual_onnx_forward_calls_final11_pages':total_forwards,'visual_review':'pending','limits':['Candidates are top-level blocks; no claim of detector recall or semantic correctness. Native/OCR source not disambiguated.','No D forward, website highlighting or compressed token inputs. Rotation/CropBox cases explicitly refused.']})
    print(f'{len(checks)} provenance/geometry checks passed;{len(pages)} real pages;{sum(types.values())} candidates;overlays saved for visual review')


if __name__=='__main__':main()
