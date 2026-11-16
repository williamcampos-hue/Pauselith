"""Owned output staging and explicit publication journal. No media algorithms."""
import hashlib,json,os,re,uuid
from datetime import datetime
from pathlib import Path

PRIMARY="Video_Sin_Silencios.mp4"
STAGE=".kiyocut-stage"
OWNER=".kiyocut-owner.json"

def atomic_bytes(path,data):
    path=Path(path);temporary=path.with_name("."+uuid.uuid4().hex[:12]+".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()

def write_json(path,value):
    atomic_bytes(path,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode("utf8"))

def read_json(path):
    value=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value,dict):raise ValueError("Se esperaba un objeto JSON: "+str(path))
    return value

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""):digest.update(block)
    return digest.hexdigest()

def job_state(jobfile):return Path(str(jobfile)+".state.json")

def create_output(jobfile,source,target,exact=None):
    source=Path(source).resolve();target=Path(target).resolve()
    if exact:
        output=Path(exact).resolve()
        if source==output or source.is_relative_to(output):raise ValueError("La salida debe estar separada del original.")
        output.mkdir(parents=True,exist_ok=False)
    else:
        target.mkdir(parents=True,exist_ok=True)
        name=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",source.stem).rstrip(" .")[:48] or "Video"
        output=target/(name+"_SinSilencios_"+datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:12])
        output.mkdir(exist_ok=False)
    owner=dict(schema=1,job=str(Path(jobfile).resolve()),input=str(source),token=uuid.uuid4().hex)
    write_json(output/OWNER,owner)
    (output/STAGE).mkdir()
    write_json(job_state(jobfile),dict(owner,output=str(output),state="processing"))
    write_json(output/"Estado.json",dict(state="processing",input=str(source)))
    return output

def owned(output,jobfile=None,token=None):
    output=Path(output)
    if output.is_symlink() or output.resolve()!=output.absolute():raise ValueError("Ruta de salida redirigida")
    owner=read_json(output/OWNER)
    if owner.get("schema")!=1 or not owner.get("token"):raise ValueError("Salida sin propietario reconocido")
    if jobfile is not None and owner["job"]!=str(Path(jobfile).resolve()):raise ValueError("Propietario de salida distinto")
    if token is not None and owner["token"]!=token:raise ValueError("Identificador de salida distinto")
    source=Path(owner["input"]).resolve()
    if source.is_relative_to(output.resolve()):raise ValueError("La salida contiene el original")
    return owner

def safe_file(output,relative):
    relative=Path(relative)
    if relative.is_absolute() or ".." in relative.parts:raise ValueError("Componente fuera de la entrega")
    path=Path(output)/relative
    if path.resolve()!=path.absolute() or not path.resolve().is_relative_to(Path(output).resolve()):raise ValueError("Componente redirigido")
    return path

def move_new(source,destination):
    # Windows rename refuses existing destinations; never replace a user's file.
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise FileExistsError(destination)
    os.rename(source,destination)

def publish(output,result,plan,settings,reporter,check=lambda:None):
    output=Path(output);owner=owned(output);stage=output/STAGE
    result=dict(result,output=str(output),video=str(output/PRIMARY))
    result["stages"]=dict(result["stages"])
    result["stages"]["publication"]={"status":"pending","reason":"Preparando componentes"}
    # Rewrite report paths before computing evidence; report failures remain partial.
    try:reporter(stage,result,plan,settings)
    except Exception as error:
        result["stages"]["report"]={"status":"fail","reason":str(error)}
        if result["state"]=="completed":result["state"]="partial"
    candidates=["Cortes.csv","Parametros_Usados.json","Informe.txt"]
    if result.get("primary_available") and result["state"]!="error":candidates.insert(0,PRIMARY)
    candidates += [str(p.relative_to(stage)) for p in (stage/"Analisis").glob("*") if p.is_file() and p.suffix in (".json",".log")]
    if result["state"]!="error":candidates += [str(p.relative_to(stage)) for p in (stage/"Clips_Individuales").glob("Clip_*.mp4")]
    files=[]
    for name in candidates:
        path=safe_file(stage,name)
        if path.is_file():files.append(dict(path=name,sha256=sha(path),size=path.stat().st_size,verified=name==PRIMARY and bool(result.get("primary_available"))))
    intent=dict(schema=1,token=owner["token"],result=result,components=files)
    check();write_json(output/"Publicacion.json",intent)
    published=[]
    try:
        for component in files:
            check();move_new(safe_file(stage,component["path"]),safe_file(output,component["path"]))
            published.append(component)
        result["stages"]["publication"]={"status":"pass","reason":"Componentes publicados", "components":published}
    except Exception as error:
        result["stages"]["publication"]={"status":"fail","reason":str(error),"components":published}
        if result["state"]=="completed":result["state"]="partial"
    primary=next((c for c in published if c["path"]==PRIMARY and c["verified"]),None)
    result["primary_available"]=primary is not None
    if primary is None and result["state"]!="error":result["state"]="error"
    if any(c["path"]=="Informe.txt" for c in published):
        try:
            reporter(output,result,plan,settings)
            for c in published:
                if c["path"] in ("Informe.txt","Analisis/Validacion_Final.json"):
                    path=output/c["path"];c.update(sha256=sha(path),size=path.stat().st_size)
        except Exception as error:
            result["stages"]["report"]={"status":"fail","reason":str(error)}
            if result["state"]=="completed":result["state"]="partial"
            os.rename(output/"Informe.txt",stage/"Informe_No_Confirmado.txt")
            published[:]=[c for c in published if c["path"]!="Informe.txt"]
    # Estado is a cache. Entrega is the authoritative multi-component commit.
    commit=dict(schema=1,token=owner["token"],result=result,components=published)
    try:
        write_json(output/"Entrega.json",commit)
        write_json(output/"Estado.json",result)
    except OSError as error:
        if result["state"]=="completed":result["state"]="partial"
        result["stages"]["finalization"]={"status":"fail","reason":str(error)}
        if any(c["path"]=="Informe.txt" for c in published):
            try:
                reporter(output,result,plan,settings)
                for c in published:
                    if c["path"] in ("Informe.txt","Analisis/Validacion_Final.json"):
                        path=output/c["path"];c.update(sha256=sha(path),size=path.stat().st_size)
            except OSError:pass
        for name,value in (("Entrega.json",commit),("Estado.json",result)):
            try:write_json(output/name,value)
            except OSError:pass
    return result


def reconcile(output,result):
    output=Path(output);owner=owned(output)
    commit=read_json(output/"Entrega.json")
    if commit["token"]!=owner["token"]:raise ValueError("Commit de otra entrega")
    commit["result"]=result
    sidecar=output/'Analisis/Validacion_Final.json'
    if sidecar.is_file() and not any(c['path']=='Analisis/Validacion_Final.json' for c in commit['components']):
        commit['components'].append(dict(path='Analisis/Validacion_Final.json',sha256=sha(sidecar),size=sidecar.stat().st_size,verified=False))
    for c in commit["components"]:
        if c["path"] in ("Informe.txt","Analisis/Validacion_Final.json"):
            path=output/c["path"];c.update(sha256=sha(path),size=path.stat().st_size)
    write_json(output/"Entrega.json",commit)

class JobLease:
    """OS releases this byte-range lock on crash; recovery never touches live jobs."""
    def __init__(self,jobfile):self.path=Path(str(jobfile)+'.lock');self.stream=None
    def __enter__(self):
        import msvcrt
        self.stream=self.path.open('a+b')
        try:
            if self.stream.tell()==0:self.stream.write(b'0');self.stream.flush()
            self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
        except BaseException:self.stream.close();raise
        return self
    def __exit__(self,*args):
        import msvcrt
        try:self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
        finally:self.stream.close()

def record_job(jobfile,result):
    path=job_state(jobfile)
    if not path.exists():return
    record=read_json(path);record.update(state=result['state'],message=result.get('message',''))
    write_json(path,record)

def recover_one(jobfile,terminal=None):
    jobfile=Path(jobfile)
    with JobLease(jobfile):
        pointer=read_json(job_state(jobfile))
        if pointer.get('output') is None:
            if pointer.get('schema')!=1 or pointer.get('job')!=str(jobfile.resolve()):raise ValueError('Solicitud no reconocida')
            result=dict(state='cancelled' if terminal=='cancelled' or Path(str(jobfile)+'.cancel').exists() else 'error',input=pointer['input'],output='',primary_available=False,recovered=True,message='Trabajo interrumpido antes de crear una salida. Añade el original para repetirlo.')
            record_job(jobfile,result);cleanup_controls(jobfile);return result
        output=Path(pointer['output'])
        owner=owned(output,jobfile,pointer['token'])
        commit=None;intent=None
        for name in ('Entrega.json','Publicacion.json'):
            try:
                data=read_json(output/name)
                if data['token']!=owner['token'] or data['schema']!=1:continue
                if not isinstance(data.get('result'),dict) or not isinstance(data.get('components'),list):raise ValueError('Manifiesto incompleto')
                if not all(isinstance(c,dict) for c in data['components']):raise ValueError('Componentes no reconocidos')
                if name=='Entrega.json':commit=data
                else:intent=data
            except (OSError,ValueError,KeyError):pass
        evidence=commit or intent
        matched=[]
        if evidence:
            for c in evidence.get('components',[]):
                try:
                    path=safe_file(output,c['path'])
                    if path.is_file() and path.stat().st_size==c['size'] and sha(path)==c['sha256']:matched.append(c)
                except (OSError,ValueError,KeyError):pass
        primary=next((c for c in matched if c['path']==PRIMARY and c.get('verified')),None)
        complete=bool(commit and len(matched)==len(commit['components']) and primary)
        state=commit['result']['state'] if complete else 'partial' if primary else 'error'
        if state not in ('completed','partial','error'):state='error'
        if not complete and (terminal=='cancelled' or Path(str(jobfile)+'.cancel').exists()):state='cancelled'
        message='Entrega validada recuperada.' if state=='completed' else 'Trabajo interrumpido. Se conservan los componentes comprobados; añade el original para procesarlo de nuevo.'
        result=dict((evidence or {}).get('result',{}),state=state,input=owner['input'],output=str(output),
                    video=str(output/PRIMARY),primary_available=bool(primary) and state in ('completed','partial'),message=message,recovered=True)
        result.setdefault('stages',{})['recovery']={'status':'pass' if complete else 'not_evaluated','reason':message,'components':matched}
        report=next((c for c in matched if c['path']=='Informe.txt'),None)
        if report and state!='completed':
            path=output/'Informe.txt'
            text=path.read_text(encoding='utf-8-sig')
            text=re.sub(r'(?m)^Estado: .*$', 'Estado: '+state, text)
            text+='\nRECUPERACION: '+state+'. '+message+'\n'
            atomic_bytes(path,text.encode('utf-8-sig'))
            report.update(sha256=sha(path),size=path.stat().st_size)
        write_json(output/'Recuperacion.json',dict(result,components=matched))
        write_json(output/'Estado.json',result)
        # A new authoritative commit records exactly the files checked above.
        if evidence:write_json(output/'Entrega.json',dict(schema=1,token=owner['token'],result=result,components=matched))
        result['cleanup']=cleanup(output)
        record_job(jobfile,result)
        cleanup_controls(jobfile)
        return result

def recover_all(jobs):
    records=[]
    for path in sorted(Path(jobs).glob('*.json.state.json')):
        jobfile=Path(str(path)[:-len('.state.json')])
        try:
            pointer=read_json(path)
            if pointer.get('state') not in ('processing','publishing'):continue
            records.append(recover_one(jobfile))
        except OSError as error:
            records.append(dict(state='recovery_warning',message='Trabajo activo o no accesible: '+str(error),job=str(jobfile)))
        except (ValueError,KeyError) as error:
            records.append(dict(state='recovery_warning',message='Metadatos no reconocidos; no se modificaron archivos: '+str(error),job=str(jobfile)))
    return records

def cleanup(output):
    """Only known disposable media in an authenticated staging tree; keep logs/unknowns."""
    output=Path(output);owned(output);stage=safe_file(output,STAGE)
    removed=[];warnings=[]
    if not stage.exists():return dict(removed=removed,warnings=warnings)
    work=safe_file(stage,'Analisis/Trabajo')
    patterns=(r'video_\d+\.mp4',r'clip_\d+\.wav',r'Pista_(Original|Editada)_\d+\.(wav|pcm)',r'videos\.ffconcat')
    candidates=[]
    if work.exists():candidates += [p for p in work.iterdir() if any(re.fullmatch(pattern,p.name) for pattern in patterns)]
    candidates += [stage/'Analisis'/name for name in ('Microfono_Original.wav','Audio_Editado_PCM.wav')]
    candidates += [stage/'Video_Audio_Completo.en_proceso.mp4']
    for path in candidates:
        try:
            checked=safe_file(output,path.relative_to(output))
            if checked.is_file():checked.unlink();removed.append(str(path.relative_to(output)))
        except (OSError,ValueError) as error:warnings.append(str(error))
    for path in (work,stage/'Clips_Individuales',stage/'Analisis',stage):
        try:
            safe_file(output,path.relative_to(output)).rmdir()
        except (OSError,ValueError):pass
    return dict(removed=removed,warnings=warnings)

def cleanup_controls(jobfile):
    for suffix in ('.ready','.cancel'):
        path=Path(str(jobfile)+suffix)
        try:path.unlink(missing_ok=True)
        except OSError:pass
