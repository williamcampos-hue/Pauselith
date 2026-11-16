"""KiyoCut local worker. Frozen cut algorithm lives in motor_original.py."""
import argparse,builtins,importlib.util,json,math,os,re,subprocess,sys,traceback,uuid,wave,time
from fractions import Fraction
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
if str(ROOT/"app") not in sys.path: sys.path.insert(0,str(ROOT/"app"))
import delivery
os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_NUM_THREADS"]="1"
FFM=ROOT/"tools/ffmpeg/ffmpeg.exe"
PROBE=ROOT/"tools/ffmpeg/ffprobe.exe"
LOG=None
CURRENT_PROGRESS=0
LOG_ERROR=None
CANCEL_FILE=None
PROGRESS_PHASE="render"

class Cancelled(BaseException):
    """Bypass validation's Exception fallbacks: cancellation is not a failed stage."""

def check_cancel():
    if CANCEL_FILE is not None and CANCEL_FILE.exists():
        raise Cancelled()

def record_cancelled(output,logpath):
    record=dict(state="cancelled",message="Proceso cancelado. Los archivos incompletos se conservan para diagnóstico; no son una entrega validada.",
                output=str(output) if output else "",log=str(logpath),primary_available=False)
    if output is not None:
        try:
            write_json(output/"Estado.json",record)
            (output/"CANCELADO.txt").write_text(record["message"],encoding="utf-8-sig")
        except OSError as error:
            record["cleanup_warning"]=str(error)
    return record
write_json=delivery.write_json

def emit(event="status",**fields):
    global CURRENT_PROGRESS,LOG_ERROR,LOG
    if "progress" in fields:
        CURRENT_PROGRESS=max(CURRENT_PROGRESS,fields["progress"])
        fields["progress"]=CURRENT_PROGRESS
    record=dict(event=event,**fields)
    terminal=event in ("done","partial","error","cancelled")
    if not terminal:check_cancel()
    if LOG:
        try:
            LOG.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n");LOG.flush()
            if terminal:LOG.close();LOG=None
        except Exception as error:
            LOG_ERROR=str(error)
            try:LOG.close()
            except Exception:pass
            LOG=None
    if terminal and LOG_ERROR:
        record["logging_warning"]=LOG_ERROR
        if record.get("state")=="completed":
            record.update(event="partial",state="partial",message="Entrega parcial: no se pudo guardar el registro.")
            record.setdefault("stages",{})["finalization"]={"status":"fail","reason":"Registro: "+LOG_ERROR}
            if record.get("output"):
                output=Path(record["output"])
                for path in (output/"Analisis/Validacion_Final.json",output/"Estado.json"):
                    try:write_json(path,record)
                    except Exception:pass
                try:
                    with (output/"Informe.txt").open("a",encoding="utf-8") as report:
                        report.write("\nESTADO FINAL: ENTREGA PARCIAL. Falló el registro de finalización.\n")
                except Exception:pass
                try:delivery.reconcile(output,record)
                except Exception:pass
    builtins.print("KIYO:"+json.dumps(record,ensure_ascii=False,allow_nan=False),flush=True)
    return record

def run(args,log=None):
    args=[str(x) for x in args]
    if PROGRESS_PHASE=="verification" and "-count_frames" in args:
        emit(progress=85,message="Comprobando número de fotogramas y duración…")
    elif PROGRESS_PHASE=="verification" and "-xerror" in args:
        emit(progress=86,message="Decodificando el video completo para detectar errores…")
    elif PROGRESS_PHASE=="verification" and "pipe:1" in args:
        emit(progress=89,message="Comparando fotogramas en los puntos de corte…")
    check_cancel()
    # communicate(timeout) drains both pipes, avoiding deadlocks on verbose FFmpeg.
    with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW) as process:
        try:
            while True:
                check_cancel()
                try:
                    stdout,stderr=process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:pass
            check_cancel()
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill();process.communicate(timeout=2)
    if log:Path(log).write_bytes(stderr)
    if process.returncode:
        details=stderr.decode("utf-8","replace")[-5000:]
        raise RuntimeError("FFmpeg/FFprobe no pudo completar la operación.\n"+details)
    return stdout
def probe(path):
    return json.loads(run([PROBE,"-v","error","-show_streams","-show_format","-of","json",path]))
def emit_engine(*parts,**kwargs):
    line=" ".join(str(x) for x in parts)
    if line.startswith("{"):
        try:data=json.loads(line)
        except ValueError:data={}
        if data.get("fase")=="plan":
            emit("plan",progress=8,message="Plan listo: {} segmentos; {:.2f} s eliminados.".format(data["clips"],data["eliminado_s"]),plan=data)
            return
        if data.get("fase")=="completo":
            emit(progress=92,message="Validaciones del motor original correctas.")
            return
    match=re.match(r"Clip (\d+)/(\d+):",line)
    if match:
        index,total=map(int,match.groups())
        emit(progress=10+int(70*index/total),message="Exportando segmento {} de {}.".format(index,total),clip=index,total_clips=total)
    elif "Validando" in line:
        emit(progress=84,message="Verificando decodificación, sincronización y puntos de corte…")
    elif line:
        emit(message=line,progress=CURRENT_PROGRESS)
def validate_settings(s):
    bounds={"threshold_db":(-90,-10),"min_silence":(.1,30),"margin":(.01,3),"min_clip":(.1,30),"crf":(0,30),"threads":(1,16),"audio_track":(1,16)}
    for k,(low,high) in bounds.items():
        if k not in s or not isinstance(s[k],(int,float)) or not math.isfinite(s[k]) or not low<=s[k]<=high:
            raise ValueError("Ajuste inválido: "+k)
    for k in ("crf","threads","audio_track"):s[k]=int(s[k])
    if s["preset"] not in ("medium","fast","slow"):raise ValueError("Preset de calidad no admitido.")
    if s["aac_bitrate"] not in ("256k","320k","192k"):raise ValueError("Bitrate de audio no admitido.")
    s["ffmpeg"]="../tools/ffmpeg/ffmpeg.exe"
    s["ffprobe"]="../tools/ffmpeg/ffprobe.exe"
    return s
def extra_tracks(source,output,info,ai,plan,engine):
    audios=[s for s in info["streams"] if s["codec_type"]=="audio"]
    if len(audios)<2:return {"preserved_audio_tracks":1,"primary_source_track":ai+1,"additional_audio":False}
    work=output/"Analisis/Trabajo";edited=[];fps=float(engine.Fraction(plan["fps"]))
    for count,(index,stream) in enumerate([(i,a) for i,a in enumerate(audios) if i!=ai],1):
        emit(progress=93,message="Conservando pista adicional {} de {}…".format(count,len(audios)-1))
        sr=int(stream["sample_rate"]);channels=int(stream["channels"])
        bits=int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample") or 16)
        width=4 if bits>16 else 2;fmt="s32le" if width==4 else "s16le"
        raw=work/("Pista_Original_%02d.pcm"%(index+1));cut=work/("Pista_Editada_%02d.pcm"%(index+1))
        # Headerless PCM avoids Python 3.11's unsupported WAVE_FORMAT_EXTENSIBLE.
        run([FFM,"-hide_banner","-nostdin","-v","error","-n","-copyts","-i",source,"-map","0:a:"+str(index),"-af","aresample={}:async=1:first_pts=0".format(sr),"-c:a","pcm_"+fmt,"-f",fmt,raw])
        frame_width=channels*width;frames=raw.stat().st_size//frame_width
        with raw.open("rb") as original,cut.open("xb") as target:
            cursor=0
            for a,b in plan["keep_frames"]:
                check_cancel();ns=round((cursor+b-a)/fps*sr)-round(cursor/fps*sr)
                original.seek(min(frames,round(a/fps*sr))*frame_width)
                remaining=ns*frame_width
                while remaining:
                    check_cancel();count=min(remaining,1048576);data=original.read(count)
                    target.write(data+bytes(count-len(data)));remaining-=count
                cursor+=b-a
        stream=dict(stream,pcm_format=fmt,lossless=sr not in (96000,88200,64000,48000,44100,32000,24000,22050,16000,12000,11025,8000,7350) or bits>16)
        edited.append((index,stream,cut))
    final=output/"Video_Sin_Silencios.mp4";temporary=output/"Video_Audio_Completo.en_proceso.mp4"
    command=[FFM,"-hide_banner","-nostdin","-v","warning","-n","-i",final]
    for _,stream,cut in edited:command+=["-f",stream["pcm_format"],"-ar",stream["sample_rate"],"-ac",stream["channels"],"-i",cut]
    command+=["-map","0:v:0","-map","0:a:0"]
    for i in range(len(edited)):command+=["-map",str(i+1)+":a:0"]
    command+=["-c:v","copy","-c:a:0","copy","-metadata:s:a:0","title=Pista original {} - principal y deteccion".format(ai+1),"-disposition:a:0","default"]
    for i,(index,stream,_) in enumerate(edited,1):
        codec="alac" if stream["lossless"] else "aac"
        command+=["-c:a:"+str(i),codec,"-ar:a:"+str(i),stream["sample_rate"]]
        if codec=="aac":command+=["-b:a:"+str(i),plan["config"]["aac_bitrate"]]
        command+=["-metadata:s:a:"+str(i),"title=Pista original {}".format(index+1),"-disposition:a:"+str(i),"0"]
    command+=["-movflags","+faststart",temporary]
    run(command,output/"Analisis/Conservar_Pistas.log")
    check=probe(temporary);tracks=[s for s in check["streams"] if s["codec_type"]=="audio"]
    if len(tracks)!=len(audios):raise RuntimeError("La exportación no conservó todas las pistas.")
    for actual,(_,source_stream,_) in zip(tracks[1:],edited):
        if int(actual["sample_rate"])!=int(source_stream["sample_rate"]) or int(actual["channels"])!=int(source_stream["channels"]):raise RuntimeError("Una pista adicional cambió frecuencia o canales.")
    for stream in tracks:
        if abs(float(stream["duration"])-plan["output_duration"])>1/fps:
            raise RuntimeError("Una pista adicional no coincide con la duración del video.")
    run([FFM,"-hide_banner","-nostdin","-v","error","-xerror","-threads","2","-i",temporary,"-map","0:a","-vn","-f","null","NUL"],output/"Analisis/Decodificacion_Todas_Las_Pistas.log")
    for i,(_,stream,cut) in enumerate(edited,1):
        if stream['lossless']:
            expected=run([FFM,'-v','error','-f',stream['pcm_format'],'-ar',stream['sample_rate'],'-ac',stream['channels'],'-i',cut,'-c:a','pcm_'+stream['pcm_format'],'-f','hash','-hash','sha256','pipe:1'])
            actual=run([FFM,'-v','error','-i',temporary,'-map','0:a:'+str(i),'-c:a','pcm_'+stream['pcm_format'],'-f','hash','-hash','sha256','pipe:1'])
            if expected!=actual:raise RuntimeError('La codificación sin pérdida no conservó las muestras de la pista adicional.')
    # Verify that stream-copy remux did not alter primary timestamps or content.
    before=probe(final); after=check
    for kind in ("video","audio"):
        old=next(s for s in before["streams"] if s["codec_type"]==kind)
        new=next(s for s in after["streams"] if s["codec_type"]==kind)
        for key in ("start_time","duration"):
            if abs(float(old[key])-float(new[key]))>.0001:raise RuntimeError("Remux alteró tiempos principales: "+key)
    for mapping,codec in (("0:v:0","rawvideo"),("0:a:0","pcm_s16le")):
        def digest(path):return run([FFM,"-v","error","-threads","2","-i",path,"-map",mapping,"-c",codec,"-threads","2","-f","hash","-hash","sha256","pipe:1"])
        if digest(final)!=digest(temporary):raise RuntimeError("Remux alteró el contenido principal")
    os.replace(temporary,final)
    return {"preserved_audio_tracks":len(tracks),"primary_source_track":ai+1,"additional_audio":True,"order":[ai+1]+[i+1 for i,_,_ in edited],"durations_s":[float(s["duration"]) for s in tracks],"sample_rates_hz":[int(s["sample_rate"]) for s in tracks],"codecs":[s["codec_name"] for s in tracks]}

def write_delivery_report(output,result,plan,settings):
    text=("KIYOCUT - RESULTADO UC-001\nEstado: {state}\nVideo: {video}\n"
          "Duracion final: {final_seconds:.6f} s\nSegundos eliminados: {removed_seconds:.6f} s\n"
          "Segmentos conservados: {clips}\n"
          "Audio: pistas independientes; sin mezcla ni cambio de ganancia.\n").format(**result)
    text+="\nEtapas:\n"
    for name,stage in result["stages"].items():
        text+="- {}: {} - {}\n".format(name,stage["status"],stage.get("reason",""))
    text+="\nValidacion: {}\n".format(result["validation_status"])
    text+="No usar una entrega parcial como si todos sus componentes estuvieran completos.\n" if result["state"]=="partial" else ""
    text+="Perfil: pista {}, {} dBFS, pausa {} s, margen {} s, clip minimo {} s.\n".format(
        settings["audio_track"],settings["threshold_db"],settings["min_silence"],settings["margin"],settings["min_clip"])
    text+="H.264 CRF {}, preset {}, AAC {}. Sin cambios al detector.\n".format(settings["crf"],settings["preset"],settings["aac_bitrate"])
    delivery.atomic_bytes(output/"Informe.txt",text.encode("utf-8-sig"))

def finish_delivery(source,output,info,plan,settings,job,engine,*,validator=None,deliver=None,reporter=None):
    """Finalize independently. No incomplete verification is promoted to success."""
    stages={key:{"status":"pending","reason":""} for key in
            ("render","verification","secondary_audio","report","finalization")}
    stages["render"]={"status":"pass","reason":"Principal exportado"}
    final=output/"Video_Sin_Silencios.mp4"
    validator=validator or engine.validate
    original_validator=validator
    def validator(*args):
        global PROGRESS_PHASE
        previous=PROGRESS_PHASE;PROGRESS_PHASE="verification"
        try:return original_validator(*args)
        finally:PROGRESS_PHASE=previous
    deliver=deliver or extra_tracks
    reporter=reporter or write_delivery_report
    try:
        verification=validator(source,final,info,plan["keep_frames"],float(Fraction(plan["fps"])),
            plan["expected_frames"],output/"Analisis/Audio_Editado_PCM.wav",output/"Analisis",plan["source_sha256"])
    except Exception as error:
        verification={"status":"not_evaluated","passed":False,"primary_playable":False,
                      "check_results":{},"reason":str(error)}
        # A broken optional check must not make an already produced principal
        # disappear. Confirm decodability separately before exposing it as usable.
        try:
            run([FFM,"-v","error","-xerror","-threads","2","-i",final,"-map","0:v:0","-map","0:a:0","-f","null","NUL"])
            verification["primary_playable"]=True
        except Exception as decode_error:
            verification.update(status="fail",reason=str(decode_error))
    stages["verification"]={"status":verification["status"],"reason":verification.get("reason",""),
                            "checks":verification.get("check_results",{})}
    if verification["status"]!="pass":
        stages["verification"]["reason"]=verification.get("reason") or "Ver detalle en Analisis/Validacion.json"
    # Failure to persist evidence is itself an incomplete delivery, not a false
    # media-corruption claim. The original check outcome is retained in result.
    evidence_error=None
    try:write_json(output/"Analisis/Validacion.json",verification)
    except Exception as error:evidence_error="No se pudo guardar validacion: "+str(error)
    tracks={"preserved_audio_tracks":1,"primary_source_track":settings["audio_track"],"additional_audio":False}
    hard_fail=verification["status"]=="fail"
    if hard_fail:
        stages["secondary_audio"]={"status":"not_evaluated","reason":"Principal no supera validacion; no se entrega como valido"}
    elif job.get("preserve_other_audio",True):
        try:
            tracks=deliver(source,output,info,settings["audio_track"]-1,plan,engine)
            stages["secondary_audio"]={"status":"pass","reason":"Pistas solicitadas verificadas",**tracks}
        except Exception as error:
            stages["secondary_audio"]={"status":"fail","reason":str(error)}
    else:stages["secondary_audio"]={"status":"pass","reason":"Pistas adicionales no solicitadas",**tracks}
    try:
        if engine.sha(source)!=plan["source_sha256"]:
            hard_fail=True
            stages["verification"]={"status":"fail","reason":"El original cambió durante el trabajo"}
    except Exception as error:
        stages["finalization"]={"status":"fail","reason":"No se pudo comprobar original: "+str(error)}
    def state():
        if hard_fail:return "error"
        return "completed" if all(s["status"]=="pass" for s in stages.values()) else "partial"
    stages["finalization"]={"status":"pass" if stages["finalization"]["status"]=="pending" and evidence_error is None else "fail",
                            "reason":evidence_error or stages["finalization"].get("reason","")}
    result=dict(state="partial",input=str(source),output=str(output),video=str(final),
                final_seconds=plan["output_duration"],removed_seconds=plan["duration"]-plan["output_duration"],
                clips=len(plan["keep_frames"]),removed_intervals=len(plan["remove_frames"]),audio=tracks,
                primary_available=not hard_fail and verification.get("primary_playable",False),
                validation_status=stages["verification"]["status"],stages=stages)
    # Reporter sees the intended terminal state; report itself is only confirmed
    # after its write succeeds. If it fails, state is downgraded to partial.
    stages["report"]={"status":"pass","reason":"Informe generado"}
    result["state"]=state()
    try:reporter(output,result,plan,settings)
    except Exception as error:
        stages["report"]={"status":"fail","reason":str(error)}
    result["state"]=state()
    return result

def process_job(a):
    global LOG,CANCEL_FILE
    job=json.loads(a.job.read_text(encoding="utf-8-sig"))
    CANCEL_FILE=Path(str(a.job)+".cancel")
    data_root=Path(os.environ.get("KIYOCUT_DATA_DIR",str(ROOT)))
    (data_root/"logs").mkdir(parents=True,exist_ok=True)
    logpath=data_root/"logs"/(a.job.stem+".log")
    LOG=logpath.open("a",encoding="utf-8")
    output=None
    try:
        # GUI releases this gate only after assigning our process to its own Job Object.
        deadline=time.monotonic()+15
        while a.ready_file and not a.ready_file.exists():
            check_cancel()
            if time.monotonic()>deadline:raise RuntimeError("La interfaz no confirmó la supervisión del proceso.")
            time.sleep(.05)
        check_cancel()
        source=Path(job["input"]).resolve()
        if not source.is_file():raise FileNotFoundError("No se encuentra el archivo: "+str(source))
        settings=validate_settings(dict(job["settings"]))
        emit(progress=1,message="Comprobando video, pistas y perfil…")
        try:
            info=probe(source)
        except RuntimeError as error:
            raise ValueError("No se pudo abrir el archivo como video. Puede no ser un video válido o estar dañado. Revisa el registro para ver el detalle técnico.") from error
        videos=[s for s in info["streams"] if s["codec_type"]=="video"]
        audios=[s for s in info["streams"] if s["codec_type"]=="audio"]
        if not videos:raise ValueError("El archivo no contiene una pista de video.")
        if not audios:raise ValueError("El video no contiene audio para detectar silencios.")
        if len(audios)==1 and settings["audio_track"]==2:
            settings["audio_track"]=1
            emit(message="Solo hay una pista de audio: se utilizará la pista 1.",progress=2)
        if settings["audio_track"]>len(audios):
            raise ValueError("Se pidió la pista {}, pero este video solo tiene {}. Cambia «Pista de voz» en Ajustes.".format(settings["audio_track"],len(audios)))
        v=videos[0]
        if v.get("color_transfer") in ("smpte2084","arib-std-b67"):
            raise ValueError("Este perfil conserva video SDR. El archivo es HDR y necesita un tratamiento de color distinto.")
        if Fraction(v["avg_frame_rate"])!=Fraction(v["r_frame_rate"]):
            raise ValueError("El archivo tiene frecuencia variable de fotogramas. El motor aprobado requiere frecuencia constante; no se convertirá automáticamente.")
        target=Path(job["output_parent"]).resolve() if job.get("output_parent") else source.parent
        output=delivery.create_output(a.job,source,target,job.get("exact_output"))
        stage=output/delivery.STAGE
        settings["input"]=str(source)
        cfgfile=stage/"Parametros_Usados.json";write_json(cfgfile,settings)
        # The original resolves tools relative to its own HERE, not to cfgfile.
        emit("started",progress=3,message="Analizando silencios con el perfil aprobado…",output=str(output),log=str(logpath))
        spec=importlib.util.spec_from_file_location("kiyo_frozen_engine",ROOT/"app/motor_original.py")
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        engine.run=run;engine.print=emit_engine
        engine.validate_original=engine.validate
        oldargv=sys.argv[:]
        try:
            sys.argv=[str(ROOT/"app/motor_original.py"),"--input",str(source),"--output",str(stage),"--config",str(cfgfile)]
            if a.plan_only:sys.argv.append("--plan-only")
            else:sys.argv.append("--render-only")
            engine.main()
        finally:sys.argv=oldargv
        plan=json.loads((stage/"Analisis/Plan.json").read_text(encoding="utf-8"))
        if a.plan_only:
            write_json(output/"Estado.json",{"state":"plan_only","input":str(source)})
            emit("done",progress=100,message="Plan de cortes calculado.",output=str(output),plan_only=True)
            return
        emit(progress=84,message="Verificando principal y completando entrega…")
        result=finish_delivery(source,stage,info,plan,settings,job,engine)
        result=delivery.publish(output,result,plan,settings,write_delivery_report,check_cancel)
        result["cleanup"]=delivery.cleanup(output)
        result["log"]=str(logpath)
        try:
            write_json(output/"Analisis/Validacion_Final.json",result)
            write_json(output/"Estado.json",result)
        except Exception as error:
            result["stages"]["finalization"]={"status":"fail","reason":str(error)}
            if result["state"]=="completed":result["state"]="partial"
            for path in (output/"Analisis/Validacion_Final.json",output/"Estado.json"):
                try:write_json(path,result)
                except Exception:pass
            try:write_delivery_report(output,result,plan,settings)
            except Exception:pass
        try:delivery.reconcile(output,result)
        except OSError as error:
            if result['state']=='completed':result['state']='partial'
            result['stages']['finalization']={'status':'fail','reason':str(error)}
        terminal=result["state"]
        event="done" if terminal=="completed" else "partial" if terminal=="partial" else "error"
        label="Terminado" if terminal=="completed" else "Entrega parcial" if terminal=="partial" else "Fallo real de validacion"
        issues=["{}: {}".format(k,s.get("reason","")) for k,s in result["stages"].items() if s["status"]!="pass"]
        acknowledgement=emit(event,progress=100,message=label+(". "+"; ".join(issues) if issues else ""),**result)
        delivery.record_job(a.job,acknowledgement)
        terminal=acknowledgement.get("state",terminal)
        if terminal!="completed":raise SystemExit(2 if terminal=="partial" else 1)
    except Cancelled:
        result=record_cancelled(output,logpath)
        if output:result['cleanup']=delivery.cleanup(output)
        delivery.record_job(a.job,result)
        emit("cancelled",**result)
        raise SystemExit(3)
    except Exception as error:
        details=traceback.format_exc()
        if LOG:
            try:LOG.write(details);LOG.flush()
            except Exception:pass
        message=str(error)
        if "frequency" in message or "frecuencia constante" in message:message="Se requiere frecuencia constante de fotogramas."
        if output and output.exists():
            write_json(output/"Estado.json",{"state":"error","message":message,"log":str(logpath)})
            (output/"ERROR.txt").write_text(message+"\n\nRegistro técnico: "+str(logpath),encoding="utf-8-sig")
        delivery.record_job(a.job,dict(state="error",message=message))
        emit("error",message=message,log=str(logpath),output=str(output) if output else "")
        sys.exit(1)
    finally:
        if output:
            try:delivery.cleanup(output)
            except Exception:pass
        if LOG:
            try:LOG.close()
            except Exception:pass
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--job",type=Path)
    parser.add_argument("--plan-only",action="store_true")
    parser.add_argument("--ready-file",type=Path)
    parser.add_argument("--recover",action="store_true")
    parser.add_argument("--settle-job",type=Path)
    parser.add_argument("--terminal",choices=("cancelled","error"),default="error")
    a=parser.parse_args()
    if a.recover:
        for result in delivery.recover_all(Path(os.environ.get("KIYOCUT_DATA_DIR",str(ROOT)))/"jobs"):emit("recovered",**result)
    elif a.settle_job:
        if delivery.job_state(a.settle_job).exists():emit("recovered",**delivery.recover_one(a.settle_job,a.terminal))
    elif a.job:
        try:
            with delivery.JobLease(a.job):process_job(a)
        finally:
            try:
                if delivery.read_json(delivery.job_state(a.job)).get('state') not in ('processing','publishing'):delivery.cleanup_controls(a.job)
            except (OSError,ValueError):pass
    else:parser.error("Se requiere --job o --recover")

if __name__=="__main__":main()
