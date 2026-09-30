"""Streaming spatial and motion-compensated quality diagnostics; no renderer changes."""
import argparse,csv,hashlib,json,math,struct,time
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from stencil_quality_common import DOC,OUT,SCENES,WINDOWS,manifest,write_sources,sha
from stencil_quality_flow import alignment_map,remap_array,run_self_test

ROIS={
 'bistro':{'chair-legs':(320,540,720,820),'foreground-boundary':(560,440,920,720),'window-rails':(880,420,1240,700)},
 'minecraft':{'stone-steps':(230,610,590,890),'foliage':(1210,735,1570,1015),'foreground-boundary':(980,250,1340,530)}}
LUMA=np.array([.2126,.7152,.0722],np.float32)
ANALYSIS_WINDOWS={'initial_still':(20,60),'moving':(60,180),'transition':(160,220),'late_still':(200,240)}


def rgb(folder,i):
    with Image.open(folder/f'frame_{i:05d}.png') as im:
        assert im.mode=='RGB' and im.size==(1920,1061),(folder,i,im.mode,im.size)
        return np.asarray(im).copy()


def edge(folder,i):
    data=(folder/f'frame_{i:05d}-edge.rg8').read_bytes()
    assert data[:4]==b'EDG1' and struct.unpack_from('<2I',data,4)==(1920,1061)
    a=np.frombuffer(data[12:],np.uint8).reshape(1061,1920,2)
    assert np.isin(a,[0,255]).all()
    return np.any(a!=0,axis=2)


def gradient(y):
    x=cv2.Sobel(y,cv2.CV_32F,1,0,ksize=3,scale=1/8)
    z=cv2.Sobel(y,cv2.CV_32F,0,1,ksize=3,scale=1/8)
    return cv2.magnitude(x,z)


def masked_mean(a,mask):
    return float(a[mask].mean(dtype=np.float64)) if np.any(mask) else None


def summarize(rows,scene,modes):
    result={}
    numeric=[k for k in rows[0] if k not in ['frame','mode','region']]
    for region in ['full',*ROIS[scene]]:
        result[region]={}
        for mode in modes:
            result[region][mode]={}
            for name,(first,end) in ANALYSIS_WINDOWS.items():
                selected=[r for r in rows if r['region']==region and r['mode']==mode and first<=r['frame']<end]
                assert len(selected)==end-first
                values={k:float(np.mean([r[k] for r in selected if r[k] is not None])) if any(r[k] is not None for r in selected) else None for k in numeric}
                mse=values['rgb_mse'];values['psnr_db']=10*math.log10(255**2/mse) if mse else None
                result[region][mode][name]=values
    return result


def settling_from_rows(rows,scene,modes):
    # Require all 40 late-still frames to match. A last-frame self-match alone
    # cannot demonstrate convergence of a periodically changing output.
    return {region:{mode:next((i-180 for i in range(180,201) if all(
        r['plateau_mismatch_fraction']==0 for r in rows
        if r['region']==region and r['mode']==mode and r['frame']>=i)),None)
        for mode in modes} for region in ['full',*ROIS[scene]]}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scene',required=True,choices=SCENES)
    ap.add_argument('--summarize-only',action='store_true',help='Rebuild summary from completed per-frame measurements; no image or flow recomputation.')
    a=ap.parse_args();scene=a.scene
    if a.summarize_only:
        path=DOC/f'{scene}-metrics.json';result=json.loads(path.read_text());assert result['validation']=='PASS'
        csv_path=DOC/f'{scene}-metrics-frames.csv'
        with csv_path.open(encoding='utf-8') as f:
            rows=[{k:(v if k in ['mode','region'] else (float(v) if v else None)) for k,v in row.items()} for row in csv.DictReader(f)]
        modes=list(result['summary']['full']);assert len(rows)==240*len(modes)*(1+len(ROIS[scene]))
        result['summary']=summarize(rows,scene,modes)
        result['settling_frames_after_180']=settling_from_rows(rows,scene,modes)
        result['settling_required_matching_tail_frames']=40
        result['per_frame_csv_sha256']=sha(csv_path)
        path.write_text(json.dumps(result,indent=2)+'\n')
        print('PASS: summary rebuilt; convergence requires all 40 late-still frames to match')
        return
    cv2.setNumThreads(2);test=run_self_test();assert test['pass']
    data=manifest(scene);modes=list(data['sequences']);regions={'full':(0,0,1920,1061),**ROIS[scene]}
    gate=json.loads((DOC/f'{scene}-cgvqm.json').read_text());assert gate['validation']=='PASS'
    folders={'SS-Reference':data['reference'],**data['sequences']}
    hashes={m:{w:hashlib.sha256() for w in ['full',*WINDOWS]} for m in folders}
    rows=[];previous_ref=None;previous_errors={};previous_rgb={};previous_mask=None
    late={m:rgb(f,i=239) for m,f in data['sequences'].items()}
    diagnostics=OUT/scene/'Diagnostics';diagnostics.mkdir(parents=True,exist_ok=True)
    t0=time.monotonic()
    for i in range(240):
        ref=rgb(data['reference'],i);ref_y=ref.astype(np.float32)@LUMA;ref_g=gradient(ref_y)
        mask=edge(data['spatial_edge'],i);toggled=np.zeros_like(mask) if previous_mask is None else mask!=previous_mask
        fields=alignment_map(previous_ref,ref,1.0) if previous_ref is not None else None
        valid_masks={}
        if fields is not None:
            mx,my=fields['map_x'],fields['map_y'];inside=(mx>=1)&(mx<=1918)&(my>=1)&(my<=1059)
            for threshold in [.5,1.,2.]:valid_masks[threshold]=inside&np.isfinite(fields['forward_backward_error'])&(fields['forward_backward_error']<=threshold)
            ref_warp=remap_array(previous_ref.astype(np.float32)@LUMA,mx,my,cv2.INTER_LINEAR)
            ref_motion_error=np.abs(ref_y-ref_warp)
            if i in [61,100,179,180,181]:
                Image.fromarray((valid_masks[1.]*255).astype(np.uint8)).save(diagnostics/f'flow-valid-{i:05d}.png')
                delta=np.clip(ref_motion_error*8,0,255).astype(np.uint8)
                Image.fromarray(delta).save(diagnostics/f'reference-warp-residual-x8-{i:05d}.png')
        # Reference hashes use the exact existing index+RGB convention.
        def add_hash(mode,pixels):
            token=i.to_bytes(8,'little')+pixels.tobytes();hashes[mode]['full'].update(token)
            for window,(lo,hi) in WINDOWS.items():
                if lo<=i<hi:hashes[mode][window].update(token)
        add_hash('SS-Reference',ref)
        for mode,folder in data['sequences'].items():
            im=rgb(folder,i);add_hash(mode,im)
            yf=im.astype(np.float32)@LUMA;err_y=yf-ref_y
            diff=im.astype(np.float32)-ref.astype(np.float32)
            mae=np.mean(np.abs(diff),axis=2);mse=np.mean(diff*diff,axis=2)
            _,smap=structural_similarity(ref_y/255,yf/255,data_range=1,gaussian_weights=True,sigma=1.5,use_sample_covariance=False,full=True)
            grad=gradient(yf);grad_error=np.abs(grad-ref_g)
            residual=None
            if fields is not None:
                residual=np.abs(err_y-remap_array(previous_errors[mode],fields['map_x'],fields['map_y'],cv2.INTER_LINEAR))
            unaligned=np.mean(np.abs(im.astype(np.float32)-previous_rgb[mode]),axis=2) if mode in previous_rgb else None
            plateau=np.mean(np.abs(im.astype(np.float32)-late[mode]),axis=2) if i>=180 else None
            for region,(l,t,r,b) in regions.items():
                sl=np.s_[t:b,l:r];edge_roi=mask[sl];toggle_roi=toggled[sl]
                row=dict(frame=i,mode=mode,region=region,
                    rgb_mae=float(mae[sl].mean(dtype=np.float64)),rgb_mse=float(mse[sl].mean(dtype=np.float64)),
                    luma_ssim=float(smap[t+5:b-5,l+5:r-5].mean(dtype=np.float64)),
                    gradient_mae=float(grad_error[sl].mean(dtype=np.float64)),gradient_mean=float(grad[sl].mean(dtype=np.float64)),
                    reference_gradient_mean=float(ref_g[sl].mean(dtype=np.float64)),
                    selected_fraction=float(edge_roi.mean()),selection_toggled_fraction=float(toggle_roi.mean()),
                    selected_rgb_mae=masked_mean(mae[sl],edge_roi),nonselected_rgb_mae=masked_mean(mae[sl],~edge_roi),
                    toggled_rgb_mae=masked_mean(mae[sl],toggle_roi),unaligned_rgb_step=float(unaligned[sl].mean()) if unaligned is not None else None,
                    plateau_rgb_mae=float(plateau[sl].mean()) if plateau is not None else None,
                    plateau_mismatch_fraction=float(np.any(im[sl]!=late[mode][sl],axis=2).mean()) if plateau is not None else None)
                for threshold in [.5,1.,2.]:
                    key={.5:'05',1.:'10',2.:'20'}[threshold]
                    row['flow_valid_'+key]=float(valid_masks[threshold][sl].mean()) if fields is not None else None
                    row['flow_error_residual_'+key]=masked_mean(residual[sl],valid_masks[threshold][sl]) if residual is not None else None
                row['reference_warp_residual']=masked_mean(ref_motion_error[sl],valid_masks[1.][sl]) if fields is not None else None
                rows.append(row)
            previous_errors[mode]=err_y;previous_rgb[mode]=im
        previous_ref=ref;previous_mask=mask
        if i%20==19:print(f'{scene} {i+1}/240 frames; {time.monotonic()-t0:.1f}s',flush=True)
    hash_values={m:{w:h.hexdigest() for w,h in windows.items()} for m,windows in hashes.items()}
    for window in WINDOWS:
        for mode in modes:
            record=gate['results'][window]['records'][mode]
            assert hash_values[mode][window]==record['test_sequence']['pixel_sha256'],(mode,window)
            assert hash_values['SS-Reference'][window]==record['reference_sequence']['pixel_sha256']
    summary=summarize(rows,scene,modes)
    settling=settling_from_rows(rows,scene,modes)
    with (DOC/f'{scene}-metrics-frames.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result=dict(validation='PASS',scene=scene,frames=240,summary=summary,settling_frames_after_180=settling,
                sequence_pixel_hashes=hash_values,rois=ROIS[scene],flow_self_test=test,
                settling_required_matching_tail_frames=40,per_frame_csv_sha256=sha(DOC/f'{scene}-metrics-frames.csv'),
                flow_reference='SS-Reference',flow_fb_thresholds=[.5,1.,2.],ssim=dict(gaussian_weights=True,sigma=1.5,use_sample_covariance=False,data_range=1,channel='BT709 coefficients on display RGB; not linear luminance'),
                metrics_units='RGB/luma errors in 0..255 code values; SSIM/coverage dimensionless; gradient is Sobel/8',
                scope='Spatial reference proxy and common-flow temporal error residual; not absolute ghosting/disocclusion ground truth. Validity excludes uncertain flow. No object-motion claim.')
    (DOC/f'{scene}-metrics.json').write_text(json.dumps(result,indent=2)+'\n');write_sources(f'{scene}-metrics-sources.json')
    print('PASS: all metric image streams match CGVQM input hashes',flush=True)


if __name__=='__main__':main()
