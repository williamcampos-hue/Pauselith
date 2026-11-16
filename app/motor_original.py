import argparse,csv,hashlib,json,math,re,subprocess,wave
from fractions import Fraction
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent

def run(args,log=None):
    r=subprocess.run([str(x) for x in args],capture_output=True)
    if log: Path(log).write_bytes(r.stderr)
    if r.returncode: raise RuntimeError(str(args)+'\n'+r.stderr.decode('utf8','replace')[-5000:])
    return r.stdout

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def probe(p,count=False):
    return json.loads(run([PROBE,'-v','error','-show_streams','-show_format','-of','json']+(['-count_frames'] if count else [])+[p]))

def complement(ranges,n):
    result=[]; cursor=0
    for a,b in ranges:
        if a>cursor: result.append((cursor,a))
        cursor=b
    if cursor<n: result.append((cursor,n))
    return result

def save(p,obj): p.write_text(json.dumps(obj,indent=2),encoding='utf8')

def main():
    global FFM,PROBE
    parser=argparse.ArgumentParser(description='Frame-aligned silence removal from microphone track; never overwrites source.')
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,default=HERE.parent)
    parser.add_argument('--config',type=Path,default=HERE/'parametros.json')
    parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--render-only',action='store_true')
    args=parser.parse_args(); cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    FFM=(HERE/cfg['ffmpeg']).resolve(); PROBE=(HERE/cfg['ffprobe']).resolve()
    src=(args.input or Path(cfg['input'])).resolve(); root=args.output.resolve()
    final=root/'Video_Sin_Silencios.mp4'; analysis=root/'Analisis'; work=analysis/'Trabajo'; clips=root/'Clips_Individuales'
    if not src.is_file(): raise FileNotFoundError(src)
    if src==final or final.exists(): raise ValueError('Elige una carpeta de salida nueva; no se sobrescribe el original ni un video final existente.')
    for p in (root,analysis,work,clips): p.mkdir(parents=True,exist_ok=True)
    original_hash=sha(src); info=probe(src); save(analysis/'FFprobe_Original.json',info)
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    audios=[s for s in info['streams'] if s['codec_type']=='audio']; ai=cfg['audio_track']-1; au=audios[ai]
    rate=Fraction(v['avg_frame_rate']); fps=float(rate); sr=int(au['sample_rate'])
    if rate!=Fraction(v['r_frame_rate']): raise ValueError('Este script requiere frecuencia constante de fotogramas.')
    frames=round(float(info['format']['duration'])*fps); duration=frames/fps
    wav=analysis/'Microfono_Original.wav'; log=analysis/'Deteccion_Silencios.log'; af=f'aresample={sr}:async=1:first_pts=0'
    run([FFM,'-hide_banner','-nostdin','-v','info','-copyts','-i',src,'-map',f'0:a:{ai}','-vn','-af',af+f",silencedetect=noise={cfg['threshold_db']}dB:d={cfg['min_silence']}",'-f','null','NUL'],log)
    run([FFM,'-hide_banner','-nostdin','-v','error','-y','-copyts','-i',src,'-map',f'0:a:{ai}','-af',af,'-c:a','pcm_s16le',wav])
    txt=log.read_text(encoding='utf8',errors='replace')
    starts=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',txt)]
    ends=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',txt)]
    if len(starts)!=len(ends): raise ValueError('Silencios sin pareja')
    remove=[]
    for s,e in zip(starts,ends):
        a=0 if s<0.001 else math.ceil((s+cfg['margin'])*fps)
        b=frames if e>=duration-.15 else math.floor((e-cfg['margin'])*fps)
        if e-s>=cfg['min_silence'] and b>a: remove.append((max(0,a),min(frames,b)))
    restored=0
    while remove:
        keep=complement(remove,frames)
        short=next(((a,b) for a,b in keep if (b-a)/fps<cfg['min_clip']),None)
        if short is None: break
        neighbours=[(i,b-a) for i,(a,b) in enumerate(remove) if b==short[0] or a==short[1]]
        if not neighbours: break
        remove.pop(min(neighbours,key=lambda x:x[1])[0]); restored+=1
    keep=complement(remove,frames)
    if not keep: raise ValueError('Sin material audible. No se produce un video vacio.')
    nf=sum(b-a for a,b in keep); final_dur=nf/fps
    plan=dict(input=str(src),source_sha256=original_hash,fps=str(rate),duration=duration,expected_frames=nf,output_duration=final_dur,keep_frames=keep,remove_frames=remove,restored_gaps=restored,config=cfg)
    save(analysis/'Plan.json',plan)
    with (root/'Cortes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter=';'); w.writerow(['Tipo','Inicio_original_s','Fin_original_s','Duracion_s','Inicio_final_s','Fin_final_s','Fotograma_inicio','Fotograma_fin_exclusivo']); t=0
        for a,b in sorted(keep+remove):
            k=(a,b) in keep; w.writerow(['CONSERVADO' if k else 'ELIMINADO',f'{a/fps:.6f}',f'{b/fps:.6f}',f'{(b-a)/fps:.6f}',f'{t/fps:.6f}' if k else '',f'{(t+b-a)/fps:.6f}' if k else '',a,b])
            if k:t+=b-a
    print(json.dumps(dict(fase='plan',clips=len(keep),intervalos_eliminados=len(remove),original_s=duration,final_s=final_dur,eliminado_s=duration-final_dur,restored_gaps=restored)),flush=True)
    if args.plan_only:return
    joined=analysis/'Audio_Editado_PCM.wav'; max_removed=-math.inf; parts=[]
    with wave.open(str(wav),'rb') as original,wave.open(str(joined),'wb') as out:
        params=original.getparams(); out.setparams(params); width=params.nchannels*params.sampwidth
        for a,b in remove:
            s=min(original.getnframes(),round(a/fps*sr)); e=min(original.getnframes(),round(b/fps*sr)); original.setpos(s)
            samples=np.frombuffer(original.readframes(e-s),dtype='<i2')
            if samples.size:
                peak=np.max(np.abs(samples.astype(np.int32)))/32768
                if peak:max_removed=max(max_removed,20*math.log10(peak))
        if max_removed>cfg['threshold_db']+3:raise ValueError(f'Pico de audio inesperado en material eliminado: {max_removed} dBFS')
        cumulative=0
        for index,(a,b) in enumerate(keep,1):
            length=b-a; ns=round((cumulative+length)/fps*sr)-round(cumulative/fps*sr)
            original.setpos(min(original.getnframes(),round(a/fps*sr))); pcm=original.readframes(ns); pcm+=bytes(max(0,ns*width-len(pcm))); out.writeframes(pcm)
            cw=work/f'clip_{index:03d}.wav'
            with wave.open(str(cw),'wb') as c:c.setparams(params);c.writeframes(pcm)
            part=work/f'video_{index:03d}.mp4'
            seek=max(0,a/fps-2-float(info['format']['start_time']))
            vf=f'trim=start={a/fps:.9f}:end={b/fps:.9f},setpts=PTS-STARTPTS'
            run([FFM,'-hide_banner','-nostdin','-v','warning','-y','-threads',str(cfg['threads']),'-copyts','-ss',f'{seek:.9f}','-i',src,'-map','0:v:0','-an','-vf',vf,'-c:v','libx264','-crf',str(cfg['crf']),'-preset',cfg['preset'],'-threads',str(cfg['threads']),'-pix_fmt','yuv420p','-profile:v','high','-r',str(rate),'-fps_mode','cfr','-video_track_timescale',str(rate.numerator),'-color_range',v.get('color_range','tv'),'-colorspace',v.get('color_space','bt709'),'-color_primaries',v.get('color_primaries','bt709'),'-color_trc',v.get('color_transfer','bt709'),'-movflags','+faststart',part],work/f'video_{index:03d}.log')
            pv=next(s for s in probe(part)['streams'] if s['codec_type']=='video')
            if int(pv['nb_frames'])!=length:raise ValueError(f'Clip {index}: {pv["nb_frames"]} != {length} fotogramas')
            if cfg['individual_clips']:
                run([FFM,'-hide_banner','-nostdin','-v','warning','-y','-i',part,'-i',cw,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a',cfg['aac_bitrate'],'-movflags','+faststart',clips/f'Clip_{index:03d}.mp4'],work/f'mux_{index:03d}.log')
            parts.append(part); cumulative+=length
            print(f'Clip {index}/{len(keep)}: {a/fps:.3f}-{b/fps:.3f} s; {length} fotogramas',flush=True)
    concat=work/'videos.ffconcat'; concat.write_text('ffconcat version 1.0\n'+''.join(f"file '{p.name}'\n" for p in parts),encoding='utf8')
    run([FFM,'-hide_banner','-nostdin','-v','warning','-n','-f','concat','-safe','0','-i',concat,'-i',joined,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a',cfg['aac_bitrate'],'-metadata:s:a:0','title=Microfono - pista original 2','-movflags','+faststart',final],analysis/'Exportacion.log')
    if args.render_only: return
    print('Exportacion completa. Validando...',flush=True)
    result=validate(src,final,info,keep,fps,nf,joined,analysis,original_hash)
    result['peak_removed_dbfs']=max_removed if math.isfinite(max_removed) else None; save(analysis/'Validacion.json',result)
    if not result['passed']:raise ValueError('Fallo de validacion: revisar Analisis/Validacion.json')
    version=run([FFM,'-version']).decode('utf8','replace').splitlines()[0]
    report=f'''FASE 1 - ELIMINACION DE SILENCIOS
Original: {src}
Video final: {final}
Duracion original: {duration:.6f} s
Duracion final de video: {final_dur:.6f} s
Segundos eliminados: {duration-final_dur:.6f} s
Intervalos eliminados: {len(remove)} (incluyen comienzo/final si corresponde)
Clips conservados: {len(keep)}; uniones interiores: {len(keep)-1}
Metodo: FFmpeg silencedetect en la pista independiente del microfono (audio 2).
Umbral {cfg['threshold_db']} dBFS; pausa minima {cfg['min_silence']} s; margen {cfg['margin']} s a cada lado.
Limites redondeados al fotograma conservando voz. Se restauraron {restored} huecos para evitar clips de menos de {cfg['min_clip']} s.
No se realizo VAD neuronal ni transcripcion: se conservan sonidos del microfono, risas y respiraciones por encima del umbral.
Pista 1 practicamente muda, descartada por instruccion del usuario. No existe gameplay audible que recuperar.
Video: {v['width']}x{v['height']}, {rate} fps, H.264 libx264 CRF {cfg['crf']}, preset {cfg['preset']}.
Audio: AAC {cfg['aac_bitrate']}, {sr} Hz, {au['channels']} canales. Misma ganancia y mezcla de pista 2.
Audio recortado en PCM y codificado una sola vez para evitar huecos y desfases acumulados entre clips.
Sin cambio de velocidad, encuadre, resolucion, efectos ni subtitulos.
Validaciones correctas: decodificacion completa, cantidad de fotogramas, duracion, resolucion, fps,
correlacion y desfase del audio cerca de cortes, comparacion de fotogramas con el original y SHA256 original intacto.
Detalles: Analisis/Validacion.json. La revision es automatica de senal y estructura, no una escucha humana ni una evaluacion semantica.
Los fotogramas se comparan contra el original para no confundir gameplay quieto con un congelamiento del render.
Herramienta: {version}
Python y NumPy. Procesamiento secuencial, {cfg['threads']} hilos de video.
Fuentes: https://ffmpeg.org/ffmpeg-filters.html#silencedetect y https://ffmpeg.org/download.html
Listo como MP4 H.264/AAC para importar en CapCut 3.6. No se modificaron proyectos de CapCut.
'''
    (root/'Informe.txt').write_text(report,encoding='utf-8-sig')
    print(json.dumps(dict(fase='completo',video=str(final),eliminado_s=duration-final_dur,cortes=len(remove),clips=len(keep),validation=result),indent=2),flush=True)

def validate(src,final,info,keep,fps,nf,reference,analysis,original_hash):
    import sys
    if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
    from validation import validate_export
    return validate_export(src,final,info,keep,fps,nf,reference,analysis,original_hash,
                           run=run,probe=probe,sha=sha,ffmpeg=FFM,ffprobe=PROBE)

if __name__=='__main__': main()