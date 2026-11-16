"""UC-001 validation only. Does not choose cuts or encode media."""
from bisect import bisect_left
from pathlib import Path
import json,math,wave
import numpy as np

class AudioMismatchError(ValueError): pass

PASS="pass"
FAIL="fail"
NE="not_evaluated"
def aggregate(results):
    statuses=[x["status"] for x in results.values()]
    return FAIL if FAIL in statuses else NE if NE in statuses else PASS
def read_timeline(ffprobe,path,run):
    data=json.loads(run([ffprobe,"-v","error","-select_streams","v:0","-show_frames",
        "-show_entries","frame=best_effort_timestamp_time","-of","json",path]))
    times=[float(x["best_effort_timestamp_time"]) for x in data["frames"]]
    if not times or not all(math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError("Missing, non-finite or non-monotonic video timestamps")
    return times
def match_time(timeline,target,tolerance):
    pos=bisect_left(timeline,target)
    candidates=[i for i in (pos-1,pos) if 0<=i<len(timeline)]
    if not candidates:return None
    best=min(candidates,key=lambda i:(abs(timeline[i]-target),i))
    return best if abs(timeline[best]-target)<=tolerance else None
def _images(ffmpeg,path,indices,run):
    unique=sorted(set(indices))
    expression="+".join("eq(n,{})".format(i) for i in unique)
    raw=run([ffmpeg,"-hide_banner","-nostdin","-v","error","-threads","2","-i",path,
        "-an","-vf","select='{}',scale=160:90,format=gray".format(expression),
        "-fps_mode","passthrough","-f","rawvideo","pipe:1"])
    if len(raw)!=len(unique)*14400:
        raise ValueError("Decoded sample count mismatch: requested={}, obtained_bytes={}".format(len(unique),len(raw)))
    frames=np.frombuffer(raw,np.uint8).reshape(-1,90,160)
    return dict(zip(unique,frames))
def visual_checks(ffmpeg,ffprobe,src,final,keep,fps,run):
    """Compare timestamp correspondence, NOT temporal frame number to decode n.
    A source gap at a sampled slot has no reliable original frame: explicitly NE.
    We never select across a cut or use an unbounded nearest-frame fallback.
    """
    result={"status":NE,"reason":"","pairs":[],"requested_samples":0,"compared_samples":0}
    try:
        st=read_timeline(ffprobe,src,run)
        try:ot=read_timeline(ffprobe,final,run)
        except ValueError as error:
            result.update(status=FAIL,reason="Invalid output PTS: "+str(error))
            return result
        result.update(source_decoded_frames=len(st),output_decoded_frames=len(ot))
        # Roundoff in stored timestamps is tolerated; an actual dropped output
        # frame or shifted output timeline is a failure, not a missing reference.
        tolerance=1/(2*fps)+1e-6
        if abs(ot[0])>1e-5 or any(abs(t-i/fps)>tolerance for i,t in enumerate(ot)):
            result.update(status=FAIL,reason="Output timeline is not the requested CFR timeline")
            return result
        bounds=[];cursor=0
        for a,b in keep:bounds.append(cursor);cursor+=b-a
        selected=sorted(set(np.linspace(0,len(keep)-1,min(12,len(keep)),dtype=int).tolist()))
        pairs=[]
        for i in selected:
            a,b=keep[i]
            for offset in sorted(set((0,b-a-1))):
                source_time=(a+offset)/fps;output_time=(bounds[i]+offset)/fps
                si=match_time(st,source_time,tolerance);oi=match_time(ot,output_time,tolerance)
                entry={"clip":i+1,"source_requested_time":source_time,"output_requested_time":output_time,
                       "source_decode_index":si,"output_decode_index":oi,"status":NE}
                if si is None or oi is None:
                    entry["reason"]="No frame at sampled timestamp within half a frame"
                elif st[si] < a/fps-1e-6 or st[si] >= b/fps:
                    # MKV millisecond rounding can place the first frame 0.333ms
                    # before the ideal boundary. Permit only half source timebase,
                    # not crossing an actual frame/cut boundary.
                    if abs(st[si]-a/fps)>.000501:
                        entry["reason"]="Nearest frame belongs outside retained segment"
                    else:entry["status"]="pending"
                else:entry["status"]="pending"
                if si is not None:entry["source_pts"]=st[si]
                if oi is not None:entry["output_pts"]=ot[oi]
                pairs.append(entry)
        result["requested_samples"]=len(pairs);result["pairs"]=pairs
        available=[p for p in pairs if p["status"]=="pending"]
        if available:
            original=_images(ffmpeg,src,[p["source_decode_index"] for p in available],run)
            output=_images(ffmpeg,final,[p["output_decode_index"] for p in available],run)
            for p in available:
                x=original[p["source_decode_index"]].astype(np.float32)
                y=output[p["output_decode_index"]].astype(np.float32)
                mse=float(np.mean((x-y)**2));score=99.0 if mse==0 else 10*math.log10(255**2/mse)
                p.update(status=PASS if score>28 else FAIL,psnr_db=score)
        result["compared_samples"]=len(available)
        result["status"]=aggregate({str(i):p for i,p in enumerate(pairs)})
        result["reason"]="Timestamp-mapped visual checks; PSNR threshold unchanged (28 dB)"
    except Exception as error:
        result.update(status=NE,reason="Visual verification unavailable: "+str(error))
    return result

def validate_export(src,final,info,keep,fps,nf,reference,analysis,original_hash,
                    *,run,probe,sha,ffmpeg=None,ffprobe=None):
    analysis=Path(analysis);analysis.mkdir(parents=True,exist_ok=True)
    if ffmpeg is None or ffprobe is None:raise ValueError("Explicit pinned FFmpeg and FFprobe required")
    results={};report={"check_results":results,"expected_frames":nf}
    def record(name,status,reason="",**data):
        results[name]=dict(status=status,reason=reason,**data)
    def check(name,value,**data):record(name,PASS if value else FAIL,**data)
    record("validation_evidence",PASS)
    def evidence(path,data):
        try:path.write_bytes(data)
        except Exception as error:
            record("validation_evidence",NE,"Could not persist auxiliary evidence: "+str(error))
    try:
        p=probe(final,True)
        evidence(analysis/"FFprobe_Final.json",json.dumps(p,indent=2).encode("utf8"))
        ov=next(s for s in p["streams"] if s["codec_type"]=="video")
        oa=next(s for s in p["streams"] if s["codec_type"]=="audio")
        sv=next(s for s in info["streams"] if s["codec_type"]=="video")
        frames=int(ov["nb_read_frames"])
        report.update(output_frames=frames,video_duration_s=float(ov["duration"]),audio_duration_s=float(oa["duration"]))
        check("frame_count_correct",frames==nf)
        check("dimensions_unchanged",(ov["width"],ov["height"])==(sv["width"],sv["height"]))
        from fractions import Fraction
        check("fps_unchanged",Fraction(ov["avg_frame_rate"])==Fraction(sv["avg_frame_rate"]))
        check("video_duration_correct",abs(float(ov["duration"])-nf/fps)<.001)
        check("audio_video_duration_aligned",abs(float(oa["duration"])-float(ov["duration"]))<1/fps
              and abs(float(oa.get("start_time",0))-float(ov.get("start_time",0)))<1/fps)
        run([ffmpeg,"-hide_banner","-nostdin","-v","error","-xerror","-threads","2",
            "-i",final,"-map","0:v:0","-map","0:a:0","-f","null","NUL"])
        evidence(analysis/"Decodificacion_Completa.log",b"")
        record("full_decode_no_errors",PASS)
    except Exception as error:
        record("full_decode_no_errors",FAIL,str(error))
    try:check("source_unchanged",sha(src)==original_hash)
    except Exception as error:record("source_unchanged",NE,str(error))
    try:
        decoded=analysis/"Audio_Final_Decodificado.wav"
        run([ffmpeg,"-hide_banner","-nostdin","-v","error","-y","-i",final,"-map","0:a:0","-c:a","pcm_s16le",decoded])
        with wave.open(str(reference),"rb") as w:
            sr,ch=w.getframerate(),w.getnchannels()
            ref=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").reshape(-1,ch).mean(axis=1)
        with wave.open(str(decoded),"rb") as w:
            if w.getframerate()!=sr or w.getnchannels()!=ch:raise AudioMismatchError("Audio rate/channel mismatch")
            actual=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").reshape(-1,ch).mean(axis=1)
        minimum=min(len(ref),len(actual))
        check("audio_length_correct",abs(len(ref)-len(actual))<sr/fps)
        if minimum==0 or np.std(ref[:minimum:8])==0 or np.std(actual[:minimum:8])==0:
            if np.std(ref[:minimum:8])>0:record("audio_correlation_correct",FAIL,"Non-silent reference became silent")
            else:record("audio_correlation_correct",NE,"Reference has no usable channel-mean signal")
            record("audio_offsets_correct",NE,"No usable signal for lag estimation")
        else:
            corr=float(np.corrcoef(ref[:minimum:8],actual[:minimum:8])[0,1])
            report["audio_correlation"]=corr if math.isfinite(corr) else None
            check("audio_correlation_correct",math.isfinite(corr) and corr>.97)
            bounds=[];cursor=0
            for a,b in keep:bounds.append(cursor);cursor+=b-a
            selected=sorted(set(np.linspace(0,len(keep)-1,min(12,len(keep)),dtype=int).tolist()))
            samples=[]
            for i in selected:
                center=round(bounds[i]/fps*sr);a=max(0,center-sr//2);b=min(minimum,center+2*sr)
                x,y=ref[a:b],actual[a:b]
                if not len(x) or np.max(np.abs(x))<100:continue
                n=1<<(2*len(x)-1).bit_length()
                corr=np.fft.irfft(np.fft.rfft(y,n)*np.conj(np.fft.rfft(x,n)),n)
                limit=round(sr*.05);lags=np.arange(-limit,limit+1)
                lag=int(lags[np.argmax(corr[lags%n])])
                samples.append(dict(clip=i+1,output_s=center/sr,offset_ms=lag/sr*1000))
            report["cut_audio_checks"]=samples
            if samples:check("audio_offsets_correct",all(abs(x["offset_ms"])<2 for x in samples))
            else:record("audio_offsets_correct",NE,"No sufficiently loud comparison windows")
    except AudioMismatchError as error:
        record("audio_correlation_correct",FAIL,str(error));record("audio_offsets_correct",NE,"Rate/channel contract violated")
    except Exception as error:
        record("audio_correlation_correct",NE,str(error));record("audio_offsets_correct",NE,str(error))
    visual=visual_checks(ffmpeg,ffprobe,src,final,keep,fps,run)
    report["visual"]=visual;report["cut_video_checks"]=visual["pairs"]
    record("cut_frames_match_source",visual["status"],visual["reason"])
    report.update(status=aggregate(results),passed=aggregate(results)==PASS,
                  checks={name:True if r["status"]==PASS else False if r["status"]==FAIL else None for name,r in results.items()},
                  primary_playable=results["full_decode_no_errors"]["status"]==PASS,
                  original_sha256=original_hash,
                  limitations="Sampled timestamp mapping, 160x90 PSNR; not a full perceptual/semantic audit.")
    return report
