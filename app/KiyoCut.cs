using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Diagnostics;
using System.Web.Script.Serialization;
using System.Runtime.InteropServices;
using System.Threading;
using System.Reflection;

[assembly: AssemblyTitle("Pauselith")]
[assembly: AssemblyProduct("Pauselith")]
[assembly: AssemblyVersion("0.9.0.1")]
[assembly: AssemblyFileVersion("0.9.0.1")]
[assembly: AssemblyInformationalVersion("0.9.0-rc.1")]

namespace KiyoCut {
static class Program {
    internal static readonly string Root=AppDomain.CurrentDomain.BaseDirectory;
    internal static readonly string DataRoot=ResolveDataRoot();
    internal static string ResolveDataRoot(){
        string custom=Environment.GetEnvironmentVariable("KIYOCUT_DATA_DIR");
        if(!String.IsNullOrWhiteSpace(custom))return Path.GetFullPath(custom);
        return File.Exists(Path.Combine(Root,"portable.mode"))?Path.Combine(Root,"data"):Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"KiyoCut");
    }
    internal static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        Application.ThreadException += (s,e) => Error(e.Exception);
        string key;
        using(var sha=System.Security.Cryptography.SHA256.Create())key=BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(DataRoot).ToUpperInvariant()))).Replace("-","");
        using(var instance=new Mutex(false,"Local\\KiyoCut_"+key)) {
            bool acquired=false;
            try {
                try{acquired=instance.WaitOne(0);}catch(AbandonedMutexException){acquired=true;}
                if(!acquired){MessageBox.Show("Pauselith ya está abierto para esta instalación.","Pauselith");return;}
                Application.Run(new MainForm(args));
            } catch(Exception ex){Error(ex);}finally{if(acquired)instance.ReleaseMutex();}
        }
    }
    internal static void Error(Exception ex) {
        try { Directory.CreateDirectory(Path.Combine(DataRoot,"logs")); File.AppendAllText(Path.Combine(DataRoot,"logs","Interfaz_Error.log"),DateTime.Now.ToString("s")+"\r\n"+ex+"\r\n",Encoding.UTF8); } catch {}
        MessageBox.Show("No se pudo completar la operación.\r\n\r\n"+ex.Message+"\r\n\r\nRegistros: "+Path.Combine(DataRoot,"logs"),"Pauselith",MessageBoxButtons.OK,MessageBoxIcon.Error);
    }
    internal static void AtomicText(string path,string text) {
        string temporary=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {
            using(var stream=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None)) {
                byte[] bytes=new UTF8Encoding(false).GetBytes(text);stream.Write(bytes,0,bytes.Length);stream.Flush(true);
            }
            if(File.Exists(path))File.Replace(temporary,path,null);else File.Move(temporary,path);
        }finally{if(File.Exists(temporary))File.Delete(temporary);}
    }
    internal static string Q(string s) { return "\""+s+"\""; }
    internal static string S(Dictionary<string,object> d,string key,string fallback="") { object v; return d.TryGetValue(key,out v)&&v!=null?Convert.ToString(v):fallback; }
    internal static bool B(Dictionary<string,object> d,string key,bool fallback=false) { object v; return d.TryGetValue(key,out v)&&v!=null?Convert.ToBoolean(v):fallback; }
    internal static void Open(string path) { if(File.Exists(path)||Directory.Exists(path)) Process.Start(new ProcessStartInfo(path){UseShellExecute=true}); }
}
class Job {
    internal string Input,Output="",Log="",Error="";
    internal bool Completed,Partial,PrimaryAvailable,Cancelled,Settled;
    internal ListViewItem Row;
    internal bool Recovered;
    internal Dictionary<string,object> Details=new Dictionary<string,object>();
}
// A private Windows Job Object owns only this task's worker and descendants.
// The worker's startup gate prevents it spawning FFmpeg before Attach succeeds.
sealed class OwnedProcesses:IDisposable {
    IntPtr handle;
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
        public long ProcessTime,JobTime;public uint Flags;
        public UIntPtr MinWorking,MaxWorking;public uint ActiveLimit;public UIntPtr Affinity;
        public uint Priority,Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong A,B,C,D,E,F; }
    [StructLayout(LayoutKind.Sequential)] struct Limits {
        public BasicLimits Basic;public IoCounters Io;
        public UIntPtr ProcessMemory,JobMemory,PeakProcess,PeakJob;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr security,string name);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int kind,ref Limits limits,uint length);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateJobObject(IntPtr job,uint code);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr job,int kind,IntPtr data,uint length,IntPtr returned);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    static Exception Failure(){return new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());}
    internal OwnedProcesses(){
        handle=CreateJobObject(IntPtr.Zero,null);if(handle==IntPtr.Zero)throw Failure();
        var limits=new Limits();limits.Basic.Flags=0x2000; // KILL_ON_JOB_CLOSE
        if(!SetInformationJobObject(handle,9,ref limits,(uint)Marshal.SizeOf(limits))){var error=Failure();Dispose();throw error;}
    }
    internal void Attach(Process process){if(!AssignProcessToJobObject(handle,process.Handle))throw Failure();}
    internal int ActiveCount {
        get {var buffer=Marshal.AllocHGlobal(48);try{
            if(!QueryInformationJobObject(handle,1,buffer,48,IntPtr.Zero))throw Failure();
            return Marshal.ReadInt32(buffer,40);
        }finally{Marshal.FreeHGlobal(buffer);}}
    }
    internal void Stop(){
        if(!TerminateJobObject(handle,3))throw Failure();
        var clock=Stopwatch.StartNew();
        while(ActiveCount>0){if(clock.ElapsedMilliseconds>5000)throw new TimeoutException("No se confirmó la terminación de los procesos de la tarea.");Thread.Sleep(25);}
    }
    public void Dispose(){if(handle!=IntPtr.Zero){CloseHandle(handle);handle=IntPtr.Zero;}}
}
partial class MainForm:Form {
    readonly ListView queue=new QueueList();
    readonly Label phase=new Label(), counter=new Label();
    readonly ProgressBar progress=new TimelineProgress();
    readonly TextBox output=new TextBox(),logbox=new TextBox();
    readonly Button start=new Button(),cancel=new Button(),settingsButton=new Button(),openVideo=new Button(),openFolder=new Button(),openLog=new Button(),chooseOutput=new Button(),resetOutput=new Button();
    readonly List<Job> jobs=new List<Job>();
    Dictionary<string,object> settings;
    Process worker;
    Task recoveryTask;
    bool running,closeAfterCancel;
    volatile bool cancelRequested;
    string cancelFile="";
    OwnedProcesses workerGroup;
    int finished;
    Job activeJob;
    int activePercent;
    readonly List<Job> processingBatch=new List<Job>();
    readonly string settingsPath=Path.Combine(Program.DataRoot,"ajustes_usuario.json");
    readonly Color accent=Color.FromArgb(0,108,104);
    public MainForm(string[] initial) {
        Directory.CreateDirectory(Path.Combine(Program.DataRoot,"jobs"));Directory.CreateDirectory(Path.Combine(Program.DataRoot,"logs"));
        settings=LoadSettings();
        BuildInterface();UpdateOpenButtons();
        Shown+=async(s,e)=>{
            start.Enabled=false;phase.Text="Comprobando trabajos interrumpidos…";
            recoveryTask=Maintenance("--recover",true);
            try{await recoveryTask;}catch(Exception ex){Log("Recuperación incompleta: "+ex.Message);}
            start.Enabled=jobs.Any(j=>j.Row.SubItems[1].Text=="Pendiente");
            foreach(var p in initial)if(!p.StartsWith("--"))AddFiles(new[]{p});
            phase.Text="Añade vídeos y pulsa Procesar vídeos. Cada original se conserva.";RefreshQueue();
        };
        FormClosing+=(s,e)=>{
            if(running) {
                e.Cancel=true;
                if(closeAfterCancel)return;
                if(MessageBox.Show("Hay un video en proceso. ¿Quieres cancelar la cola y cerrar?","Pauselith",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
                closeAfterCancel=true;CancelQueue();
            }
        };
    }
    Button Btn(string label,int width){return new Button{Text=label,Width=width,Height=34,Margin=new Padding(0,3,8,3)};}
    void Ui(Action a){if(IsDisposed||!IsHandleCreated)return;try{BeginInvoke(a);}catch(InvalidOperationException){}}
    void Log(string line){logbox.AppendText(DateTime.Now.ToString("HH:mm:ss")+"  "+line+Environment.NewLine);}
    void EnableDrop(Control c) {
        c.AllowDrop=true;
        c.DragEnter+=(s,e)=>{e.Effect=e.Data.GetDataPresent(DataFormats.FileDrop)?DragDropEffects.Copy:DragDropEffects.None;};
        c.DragDrop+=(s,e)=>{if(e.Data.GetDataPresent(DataFormats.FileDrop))AddFiles((string[])e.Data.GetData(DataFormats.FileDrop));};
    }
    void AddDialog(){using(var d=new OpenFileDialog{Title="Selecciona una o varias grabaciones",Filter="Videos|*.mkv;*.mp4;*.mov;*.avi;*.m4v;*.webm;*.wmv;*.flv;*.ts;*.mts;*.m2ts|Todos los archivos|*.*",Multiselect=true}){if(d.ShowDialog(this)==DialogResult.OK)AddFiles(d.FileNames);}}
    void AddFiles(IEnumerable<string> files) {
        int added=0,rejected=0,duplicates=0;string lastError="No se añadieron vídeos.";
        foreach(var candidate in files) {
            string path;
            try{path=Path.GetFullPath(candidate);}catch{rejected++;lastError="La ruta de uno de los archivos no es válida.";Log(lastError);continue;}
            if(!File.Exists(path)){rejected++;lastError="No se encuentra el archivo: "+Path.GetFileName(path);Log(lastError);continue;}
            if(jobs.Any(j=>String.Equals(j.Input,path,StringComparison.OrdinalIgnoreCase)&&(j.Row.SubItems[1].Text=="Pendiente"||j.Row.SubItems[1].Text.StartsWith("Procesando")))){duplicates++;continue;}
            bool supported=new[]{".mkv",".mp4",".mov",".avi",".m4v",".webm",".wmv",".flv",".ts",".mts",".m2ts"}.Contains(Path.GetExtension(path).ToLowerInvariant());
            var job=new Job{Input=path};var row=new ListViewItem(new[]{Path.GetFileName(path),"Pendiente","",""});row.Tag=job;row.ToolTipText=path;job.Row=row;jobs.Add(job);queue.Items.Add(row);
            if(supported){added++;if(running)processingBatch.Add(job);}
            else{rejected++;lastError="Formato no compatible. Usa un vídeo MP4, MKV, MOV u otro formato indicado.";job.Settled=true;job.Error=lastError;row.SubItems[1].Text="Error";row.ForeColor=Visual.Bad;row.ToolTipText=path+"\r\n"+lastError;Log(lastError+" "+Path.GetFileName(path));}
        }
        if(!running)phase.Text=rejected>0?(added>0?String.Format("{0} añadidos · {1} no se pudieron importar. Revisa los detalles.",added,rejected):lastError):added>0?String.Format("{0} vídeo(s) añadidos. Pulsa Procesar vídeos para empezar.",added):duplicates>0?"Estos vídeos ya están pendientes o en proceso.":lastError;
        if(queue.SelectedItems.Count==0&&queue.Items.Count>0)queue.Items[queue.Items.Count-1].Selected=true;
        UpdateOpenButtons();
    }
    Job Selected(){return queue.SelectedItems.Count>0?queue.SelectedItems[0].Tag as Job:null;}
    void UpdateOpenButtons(){RefreshQueue();RefreshResult();var j=Selected();openVideo.Enabled=j!=null&&(j.Completed||(j.Partial&&j.PrimaryAvailable));openFolder.Enabled=j!=null&&Directory.Exists(j.Output);openLog.Enabled=j!=null&&File.Exists(j.Log);}
    void OpenSelected(bool video){var j=Selected();if(j==null)return;Program.Open(video?Path.Combine(j.Output,"Video_Sin_Silencios.mp4"):j.Output);}
    void RemoveSelected(){foreach(ListViewItem row in queue.SelectedItems.Cast<ListViewItem>().ToArray()){if(row.SubItems[1].Text.StartsWith("Procesando"))continue;jobs.Remove((Job)row.Tag);queue.Items.Remove(row);}UpdateOpenButtons();}
    void ClearFinished(){foreach(var j in jobs.Where(j=>j.Completed||j.Partial||j.Row.SubItems[1].Text=="Error"||j.Row.SubItems[1].Text=="Cancelado").ToArray()){queue.Items.Remove(j.Row);jobs.Remove(j);}UpdateOpenButtons();}
    Dictionary<string,object> LoadSettings() {
        var defaults=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Program.Root,"perfil_probado.json"),Encoding.UTF8));
        if(File.Exists(settingsPath))try{var saved=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(settingsPath,Encoding.UTF8));foreach(var pair in saved)defaults[pair.Key]=pair.Value;}catch{}
        return defaults;
    }
    void SaveSettings(){Program.AtomicText(settingsPath,Program.Json.Serialize(settings));}
    void ChooseOutput(){using(var d=new FolderBrowserDialog{Description="Carpeta donde se crearán las carpetas de resultados",SelectedPath=Program.S(settings,"output_parent"),ShowNewFolderButton=true}){if(d.ShowDialog(this)==DialogResult.OK){output.Text=d.SelectedPath;ApplyDestination();}}}
    void EditSettings(){using(var d=new SettingsForm(settings)){if(d.ShowDialog(this)==DialogResult.OK){settings=d.Result;output.Text=Program.S(settings,"output_parent");SaveSettings();RefreshProfile();Log("Ajustes guardados para los próximos videos.");phase.Text="Ajustes guardados. Puedes restaurar el perfil original cuando quieras.";}}}
    async Task ProcessQueue() {
        if(running)return;
        if(recoveryTask!=null&&!recoveryTask.IsCompleted){phase.Text="Espera a que termine la recuperación inicial.";return;}
        if(!jobs.Any(j=>j.Row.SubItems[1].Text=="Pendiente")){phase.Text="Añade al menos un video pendiente.";return;}
        if(!ApplyDestination()){phase.Text="Corrige la carpeta de salida antes de procesar.";output.Focus();return;}
        processingBatch.Clear();processingBatch.AddRange(jobs.Where(j=>j.Row.SubItems[1].Text=="Pendiente"));
        running=true;cancelRequested=false;finished=0;start.Enabled=false;cancel.Enabled=true;settingsButton.Enabled=false;chooseOutput.Enabled=false;resetOutput.Enabled=false;output.Enabled=false;
        try {
            while(!cancelRequested) {
                var job=jobs.FirstOrDefault(j=>j.Row.SubItems[1].Text=="Pendiente");if(job==null)break;
                activeJob=job;activePercent=0;queue.SelectedItems.Clear();job.Row.Selected=true;job.Row.EnsureVisible();job.Row.SubItems[1].Text="Procesando";RefreshProgress();
                phase.Text="Preparando "+Path.GetFileName(job.Input);Log(phase.Text);
                string id=DateTime.Now.ToString("yyyyMMdd_HHmmss_")+Guid.NewGuid().ToString("N");
                string jobpath=Path.Combine(Program.DataRoot,"jobs",id+".json");
                cancelFile=jobpath+".cancel";string readyFile=jobpath+".ready";
                var snapshot=Program.Json.Deserialize<Dictionary<string,object>>(Program.Json.Serialize(settings));
                var request=new Dictionary<string,object>{{"input",job.Input},{"output_parent",output.Text},{"settings",snapshot},{"preserve_other_audio",Program.B(snapshot,"preserve_other_audio",true)}};
                Program.AtomicText(jobpath+".state.json",Program.Json.Serialize(new Dictionary<string,object>{{"schema",1},{"job",Path.GetFullPath(jobpath)},{"input",job.Input},{"output",null},{"state","processing"}}));
                Program.AtomicText(jobpath,Program.Json.Serialize(request));
                int code=-1;var errors=new StringBuilder();
                try {
                    var process=new Process();worker=process;
                    process.StartInfo=new ProcessStartInfo(Path.Combine(Program.Root,"runtime","python","python.exe"),"-B -X utf8 -u "+Program.Q(Path.Combine(Program.Root,"app","worker.py"))+" --job "+Program.Q(jobpath)+" --ready-file "+Program.Q(readyFile));
                    process.StartInfo.UseShellExecute=false;process.StartInfo.CreateNoWindow=true;process.StartInfo.RedirectStandardOutput=true;process.StartInfo.RedirectStandardError=true;process.StartInfo.StandardOutputEncoding=Encoding.UTF8;process.StartInfo.StandardErrorEncoding=Encoding.UTF8;process.StartInfo.WorkingDirectory=Program.Root;
                    process.StartInfo.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
                    process.StartInfo.EnvironmentVariables["KIYOCUT_DATA_DIR"]=Program.DataRoot;
                    process.StartInfo.EnvironmentVariables["OPENBLAS_NUM_THREADS"]="1";process.StartInfo.EnvironmentVariables["OMP_NUM_THREADS"]="1";
                    process.OutputDataReceived+=(s,e)=>{if(e.Data!=null)OnEvent(job,e.Data);};
                    process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)lock(errors){if(errors.Length<16000)errors.AppendLine(e.Data);}};
                    code=await Task.Run(()=>{
                        bool started=false,attached=false;
                        using(var group=new OwnedProcesses())try {
                            workerGroup=group;
                            process.Start();started=true;group.Attach(process);attached=true;
                            process.BeginOutputReadLine();process.BeginErrorReadLine();
                            File.WriteAllText(readyFile,"");
                            var cancellation=new Stopwatch();
                            while(!process.WaitForExit(100)) {
                                if(cancelRequested&&!cancellation.IsRunning)cancellation.Start();
                                if(cancellation.ElapsedMilliseconds>=8000){group.Stop();break;}
                            }
                            // Also reclaim descendants if a worker exits unexpectedly.
                            group.Stop();
                            if(!process.WaitForExit(2000))throw new TimeoutException("El worker no confirmó su cierre.");
                            if(!Task.Run(()=>process.WaitForExit()).Wait(2000))throw new TimeoutException("No se cerraron los canales del worker.");
                            return process.ExitCode;
                        } finally {
                            if(started&&!attached){try{process.Kill();process.WaitForExit(2000);}catch{}}
                            workerGroup=null;
                        }
                    });
                } catch(Exception ex) {job.Error=ex.Message;}
                finally{if(worker!=null){worker.Dispose();worker=null;}}
                if(!(code==0&&job.Completed)&&!(code==2&&job.Partial))try {
                    var recovered=await Maintenance("--settle-job "+Program.Q(jobpath)+" --terminal "+(cancelRequested?"cancelled":"error"),false);
                    if(recovered!=null) {
                        job.Details=recovered;job.Recovered=Program.B(recovered,"recovered");
                        string state=Program.S(recovered,"state");
                        job.Output=Program.S(recovered,"output",job.Output);job.PrimaryAvailable=Program.B(recovered,"primary_available");
                        if(state=="completed"){job.Completed=true;code=0;}
                        else if(state=="partial"){job.Partial=true;code=2;job.Error=Program.S(recovered,"message");}
                        else if(state=="cancelled"){job.Cancelled=true;code=3;}
                    }
                }catch(Exception ex){Log("No se pudo reconciliar la entrega: "+ex.Message);}
                job.Settled=true;
                if((code==3||job.Cancelled||cancelRequested)&&!(code==0&&job.Completed)&&!(code==2&&job.Partial)&&code!=-1) {
                    job.Completed=false;job.Partial=false;job.PrimaryAvailable=false;job.Cancelled=true;
                    job.Row.SubItems[1].Text="Cancelado";job.Row.ForeColor=Visual.Warn;Log("Cancelado: "+Path.GetFileName(job.Input));
                } else if(code==2&&job.Partial) {
                    job.Row.SubItems[1].Text="Entrega parcial";job.Row.ForeColor=Visual.Warn;progress.Value=100;
                    Log("ENTREGA PARCIAL: "+job.Error);job.Row.ToolTipText=job.Input+"\r\n"+job.Error;
                } else if(code==0&&job.Completed) {
                    job.Row.SubItems[1].Text="Terminado";job.Row.ForeColor=Visual.Good;finished++;progress.Value=100;Log("Terminado: "+Path.GetFileName(job.Input));
                } else {
                    job.Row.SubItems[1].Text="Error";job.Row.ForeColor=Visual.Bad;
                    if(String.IsNullOrEmpty(job.Error))job.Error=errors.Length>0?errors.ToString():"El proceso terminó sin confirmar una exportación válida.";
                    Log("ERROR: "+job.Error);job.Row.ToolTipText=job.Input+"\r\n"+job.Error;
                }
                RefreshQueue();
                UpdateOpenButtons();
            }
        } catch(Exception ex){Program.Error(ex);}
        finally{running=false;if(worker!=null){worker.Dispose();worker=null;}cancelFile="";start.Enabled=true;cancel.Enabled=false;settingsButton.Enabled=true;chooseOutput.Enabled=true;resetOutput.Enabled=true;output.Enabled=true;phase.Text=cancelRequested?"Cola cancelada. Los videos pendientes pueden procesarse de nuevo; añade otra vez el cancelado para repetirlo.":"Cola terminada. Selecciona un resultado para abrir el video o su carpeta.";UpdateOpenButtons();if(closeAfterCancel)BeginInvoke(new Action(Close));}
    }
    async Task<Dictionary<string,object>> Maintenance(string arguments,bool restoreRows) {
        string text=await Task.Run(()=>{
            using(var process=new Process())using(var group=new OwnedProcesses()) {
                process.StartInfo=new ProcessStartInfo(Path.Combine(Program.Root,"runtime","python","python.exe"),"-I -B -X utf8 "+Program.Q(Path.Combine(Program.Root,"app","worker.py"))+" "+arguments){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8,WorkingDirectory=Program.Root};
                process.StartInfo.EnvironmentVariables["KIYOCUT_DATA_DIR"]=Program.DataRoot;
                process.Start();
                try {
                    group.Attach(process);
                    var stdout=process.StandardOutput.ReadToEndAsync();var stderr=process.StandardError.ReadToEndAsync();
                    if(!process.WaitForExit(60000)){group.Stop();throw new TimeoutException("La recuperación excedió su tiempo máximo; se conservaron los archivos.");}
                    group.Stop();
                    if(!Task.WaitAll(new Task[]{stdout,stderr},2000))throw new TimeoutException("Canales de recuperación sin cerrar.");
                    if(process.ExitCode!=0)throw new Exception(stderr.Result);
                    return stdout.Result;
                }finally{if(!process.HasExited){process.Kill();process.WaitForExit(2000);}}
            }
        });
        Dictionary<string,object> last=null;
        foreach(string line in text.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries)) {
            if(!line.StartsWith("KIYO:"))continue;
            var data=Program.Json.Deserialize<Dictionary<string,object>>(line.Substring(5));last=data;
            Log(Program.S(data,"message","Recuperación comprobada."));
            if(restoreRows&&data.ContainsKey("input")) {
                string state=Program.S(data,"state");var job=new Job{Input=Program.S(data,"input"),Output=Program.S(data,"output"),Completed=state=="completed",Partial=state=="partial",Cancelled=state=="cancelled",PrimaryAvailable=Program.B(data,"primary_available"),Settled=true,Recovered=true,Details=data};
                job.Row=new ListViewItem(new[]{Path.GetFileName(job.Input),job.Completed?"Terminado":job.Partial?"Entrega parcial":job.Cancelled?"Cancelado":"Error","",job.Output});job.Row.Tag=job;job.Row.ToolTipText=Program.S(data,"message");jobs.Add(job);queue.Items.Add(job.Row);
            }
        }
        UpdateOpenButtons();return last;
    }
    void OnEvent(Job job,string line) {
        if(!line.StartsWith("KIYO:")){Ui(()=>Log(line));return;}
        Dictionary<string,object> data;
        try{data=Program.Json.Deserialize<Dictionary<string,object>>(line.Substring(5));}catch{Ui(()=>Log(line));return;}
        var ev=Program.S(data,"event");string message=Program.S(data,"message");
        if(data.ContainsKey("output"))job.Output=Program.S(data,"output");
        if(data.ContainsKey("log"))job.Log=Program.S(data,"log");
        if(ev=="done"&&Program.S(data,"state")=="completed")job.Completed=true;
        if(ev=="partial"&&Program.S(data,"state")=="partial"){job.Partial=true;job.PrimaryAvailable=Program.B(data,"primary_available");job.Error=message;}
        if(ev=="cancelled")job.Cancelled=true;
        if(ev=="done"||ev=="partial"||ev=="error"||ev=="cancelled")job.Details=data;
        if(ev=="error")job.Error=message;
        Ui(()=>{
            if(job.Settled)return;
            if(data.ContainsKey("progress")){int value=Math.Max(0,Math.Min(99,Convert.ToInt32(data["progress"])));if(job==activeJob)activePercent=value;if(!job.Completed&&!job.Partial&&!job.Cancelled)job.Row.SubItems[1].Text="Procesando "+value+" %";}
            if(!String.IsNullOrEmpty(message)){phase.Text=message;Log(message);}
            job.Row.SubItems[3].Text=job.Output;
            if(data.ContainsKey("final_seconds")){double secs=Convert.ToDouble(data["final_seconds"]);var t=TimeSpan.FromSeconds(secs);job.Row.SubItems[2].Text=Visual.Time(secs);}
            UpdateOpenButtons();
        });
    }
    void CancelQueue() {
        cancelRequested=true;cancel.Enabled=false;phase.Text="Cancelando el proceso actual…";
        // The request exists even if cancellation races with process startup.
        if(!String.IsNullOrEmpty(cancelFile))try{File.WriteAllText(cancelFile,"");}
        catch(Exception ex){Log("No se pudo enviar la solicitud; se usará el cierre supervisado: "+ex.Message);}
    }
}
}
