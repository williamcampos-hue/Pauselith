// Automated integration of the real WinForms queue; no manual UI interaction.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Drawing;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using KiyoCut;
class CancellationHarness {
    const BindingFlags Flags=BindingFlags.Instance|BindingFlags.NonPublic;
    static object Get(object value,string name){return value.GetType().GetField(name,Flags).GetValue(value);}
    static void Set(object value,string name,object data){value.GetType().GetField(name,Flags).SetValue(value,data);}
    static object Call(object value,string name,params object[] args){return value.GetType().GetMethod(name,Flags).Invoke(value,args);}
    static void Assert(bool value,string message){if(!value)throw new Exception(message);}
    static void Until(Func<bool> condition,int timeout,string message){
        var timer=Stopwatch.StartNew();
        while(!condition()){Application.DoEvents();if(timer.ElapsedMilliseconds>timeout)throw new TimeoutException(message);Thread.Sleep(5);}
        Application.DoEvents();
    }
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr job,int kind,IntPtr data,uint length,IntPtr returned);
    static int[] Pids(MainForm form){
        var group=Get(form,"workerGroup");if(group==null)return new int[0];
        var handle=(IntPtr)Get(group,"handle");var memory=Marshal.AllocHGlobal(1032);
        try {
            if(!QueryInformationJobObject(handle,3,memory,1032,IntPtr.Zero))return new int[0];
            int count=Marshal.ReadInt32(memory,4);var ids=new List<int>();
            for(int i=0;i<count;i++)ids.Add((int)Marshal.ReadIntPtr(memory,8+i*IntPtr.Size));
            return ids.ToArray();
        } finally{Marshal.FreeHGlobal(memory);}
    }
    static bool Alive(int id){try{using(var process=Process.GetProcessById(id))return !process.HasExited;}catch(ArgumentException){return false;}}
    static List<Job> Jobs(MainForm form){return (List<Job>)Get(form,"jobs");}
    static MainForm Form(string output,params string[] inputs){
        Directory.CreateDirectory(output);
        var form=new MainForm(new string[0]);form.ShowInTaskbar=false;form.WindowState=FormWindowState.Minimized;form.Show();Application.DoEvents();
        var recovery=Get(form,"recoveryTask") as Task;if(recovery!=null)Finish(recovery);
        ((TextBox)Get(form,"output")).Text=output;
        Call(form,"AddFiles",new object[]{inputs});return form;
    }
    static Task Start(MainForm form){return (Task)Call(form,"ProcessQueue");}
    static void Finish(Task task){Until(()=>task.IsCompleted,20000,"Queue did not finish within 20 seconds");task.GetAwaiter().GetResult();}
    static void State(Job job,string expected){Assert(job.Row.SubItems[1].Text==expected,"Expected "+expected+", got "+job.Row.SubItems[1].Text+": "+job.Error);}
    [STAThread] static int Main(string[] args){
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.ThrowException);Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        string root=AppDomain.CurrentDomain.BaseDirectory,worker=Path.Combine(root,"app","worker.py"),real=File.ReadAllText(worker);
        Process unrelated=null;MainForm current=null;
        try {
            if(args.Length>2&&args[2]=="--ux-only") {UxContracts(args[1],File.ReadAllText(Path.Combine(root,"valid-result-path.txt")));return 0;}
            if(args.Length>2&&args[2]=="--crash") {
                current=Form(Path.Combine(root,"crash-results"),args[0]);var active=Start(current);int[] ids=new int[0];
                Until(()=>{ids=Pids(current);return ids.Length>=2&&Jobs(current)[0].Output!="";},12000,"Crash fixture did not reach active processing");
                File.WriteAllText(Path.Combine(root,"crash-ready.json"),Program.Json.Serialize(new Dictionary<string,object>{{"pids",ids},{"output",Jobs(current)[0].Output}}));
                while(true){Application.DoEvents();Thread.Sleep(10);}
            }
            if(args.Length>2&&args[2]=="--reopen") {
                current=Form(Path.Combine(root,"reopen-results"),args[1]);
                Assert(Jobs(current).Any(j=>j.Row.SubItems[1].Text=="Error"||j.Partial),"Startup did not surface the interrupted job");
                Finish(Start(current));State(Jobs(current).Last(),"Terminado");current.Close();current=null;
                Console.WriteLine("PASS unexpected application death, automatic startup recovery and new successful job");return 0;
            }
            unrelated=Process.Start(new ProcessStartInfo(Path.Combine(root,"runtime","python","python.exe"),"-I -B -c \"import time; time.sleep(120)\""){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true});
            string outputs=Path.Combine(root,"results");Directory.CreateDirectory(outputs);
            string originalHash=Hash(args[0]),shortHash=Hash(args[1]);
            current=Form(outputs,args[0],args[1]);var queue=Start(current);int[] owned=new int[0];
            Until(()=>{owned=Pids(current);return Jobs(current)[0].Output!=""&&owned.Length>=2;},12000,"Real worker did not enter a subprocess stage");
            Call(current,"CancelQueue");Finish(queue);Console.WriteLine("TRACE queue settled after cancellation");
            State(Jobs(current)[0],"Cancelado");State(Jobs(current)[1],"Pendiente");
            Assert(((ProgressBar)Get(current,"progress")).Value==0&&((ProgressBar)Get(current,"queueProgress")).Value==0,"Cancelled batch left stale progress with pending work");
            Assert(!Jobs(current)[0].Completed&&!Jobs(current)[0].Partial,"Cancelled job exposed as delivered");
            Assert(owned.All(id=>!Alive(id)),"Owned process survived cooperative cancellation");
            Assert(!unrelated.HasExited,"Unrelated process was terminated");
            Assert(!((bool)Get(current,"running"))&&((Button)Get(current,"start")).Enabled,"UI did not recover");
            Assert(File.ReadAllText(Path.Combine(Jobs(current)[0].Output,"Estado.json")).Contains("cancelled"),"Cancelled status not persisted");
            Console.WriteLine("TRACE resuming pending job");Finish(Start(current));State(Jobs(current)[1],"Terminado");
            Assert(File.Exists(Path.Combine(Program.DataRoot,"ajustes_usuario.json")),"Settings not written to user data");
            Assert(!File.Exists(Path.Combine(Program.Root,"ajustes_usuario.json")),"Settings leaked into application files");
            Assert(Directory.GetFiles(Path.Combine(Program.DataRoot,"logs")).Length>0,"Worker logs not written to user data");
            Assert(((ProgressBar)Get(current,"queueProgress")).Value==100,"Settled resumed batch did not complete queue progress");
            string valid=Path.Combine(Jobs(current)[1].Output,"Video_Sin_Silencios.mp4"),validHash=Hash(valid);
            File.WriteAllText(Path.Combine(root,"valid-result-path.txt"),valid);current.Close();current=null;
            Console.WriteLine("PASS real cancellation, descendants, pending queue, resumed successful export");
            UxContracts(args[1],valid);

            // A deliberately unresponsive worker tests the bounded fallback and close deferral.
            File.Copy(Path.Combine(root,"unresponsive.py"),worker,true);
            current=Form(outputs,args[0]);queue=Start(current);
            Until(()=>{owned=Pids(current);return Jobs(current)[0].Output!=""&&owned.Length>=2;},8000,"Unresponsive worker did not start");
            Call(current,"CancelQueue");Set(current,"closeAfterCancel",true);current.Close();
            Assert(!current.IsDisposed,"Window closed before cleanup");
            Finish(queue);Until(()=>current.IsDisposed,2000,"Deferred close did not finish");
            Assert(owned.All(id=>!Alive(id)),"Descendant survived forced cancellation");
            State(Jobs(current)[0],"Cancelado");Assert(!unrelated.HasExited,"Fallback killed unrelated process");
            Assert(Hash(valid)==validHash,"Previous successful export changed");current=null;
            Console.WriteLine("PASS forced tree termination, bounded wait, deferred close, previous output preserved");

            File.WriteAllText(worker,real);
            current=Form(outputs,args[0]);queue=Start(current);Call(current,"CancelQueue");Finish(queue);
            State(Jobs(current)[0],"Cancelado");current.Close();current=null;
            Console.WriteLine("PASS cancellation racing with startup");

            File.Copy(Path.Combine(root,"completed.py"),worker,true);
            current=Form(outputs,args[1]);queue=Start(current);
            Until(()=>Jobs(current)[0].Completed,8000,"Completed acknowledgement missing");
            Call(current,"CancelQueue");Finish(queue);State(Jobs(current)[0],"Terminado");
            Assert(Hash(valid)==validHash,"Late cancellation changed valid output");current.Close();current=null;
            Assert(Hash(args[0])==originalHash&&Hash(args[1])==shortHash,"Original input modified");
            Assert(!unrelated.HasExited,"Unrelated sentinel terminated");
            Console.WriteLine("PASS committed-result race and original SHA256 integrity");return 0;
        } catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally {
            File.WriteAllText(worker,real);
            try {
                if(current!=null&&!current.IsDisposed){Set(current,"closeAfterCancel",true);Call(current,"CancelQueue");Until(()=>!(bool)Get(current,"running"),20000,"Cleanup timed out");current.Close();}
            } finally {
                if(unrelated!=null){if(!unrelated.HasExited){unrelated.Kill();unrelated.WaitForExit(2000);}unrelated.Dispose();}
            }
        }
    }
    static void UxContracts(string input,string valid) {
        ThemeContracts();
        using(var form=Form(Path.Combine(Program.Root,"ux-results"),input)) {
            var list=(ListView)Get(form,"queue");var job=Jobs(form).Last();job.Row.Selected=true;Call(form,"UpdateOpenButtons");
            Assert(((Button)Get(form,"start")).Enabled,"Pending input did not enable primary action");
            int count=Jobs(form).Count;Call(form,"AddFiles",new object[]{new[]{input}});Assert(Jobs(form).Count==count,"Duplicate pending file accepted");
            Call(form,"AddFiles",new object[]{new[]{Path.Combine(Program.Root,"missing.mp4")}});
            Assert(((Label)Get(form,"phase")).Text.Contains("No se encuentra"),"Missing-file import falsely reported success");
            string invalid=Path.Combine(Program.Root,"not-a-video.txt");File.WriteAllText(invalid,"synthetic invalid file");
            Call(form,"AddFiles",new object[]{new[]{invalid}});var rejected=Jobs(form).Last();State(rejected,"Error");
            list.SelectedItems.Clear();job.Row.Selected=true;
            var result=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Path.GetDirectoryName(valid),"Estado.json")));
            result["state"]="partial";result["primary_available"]=true;
            result["stages"]=new Dictionary<string,object>{{"secondary_audio",new Dictionary<string,object>{{"status","fail"},{"reason","Injected missing secondary track"}}}};
            result["event"]="partial";result["message"]="Entrega parcial";
            Call(form,"OnEvent",job,"KIYO:"+Program.Json.Serialize(result));
            job.Settled=true;job.Row.SubItems[1].Text="Entrega parcial";Call(form,"UpdateOpenButtons");Application.DoEvents();
            Assert(((Button)Get(form,"openVideo")).Enabled,"Valid partial principal cannot be opened");
            Assert(((Label)Get(form,"resultNotice")).Text.Contains("Entrega parcial"),"Partial warning missing");
            Assert(((Label)Get(form,"tracksLabel")).Text.Contains("faltan pistas"),"Secondary audio failure hidden");
            Assert(((Label)Get(form,"finalValue")).Text==Visual.Time(ResultView.Number(result,"final_seconds")),"UI did not show worker duration");
            result["state"]="error";result["primary_available"]=false;job.Partial=false;job.Row.SubItems[1].Text="Error";job.Details=result;Call(form,"UpdateOpenButtons");
            Assert(!((Button)Get(form,"openVideo")).Enabled,"Unconfirmed principal can be opened");
            Assert(((Label)Get(form,"tracksLabel")).Text.Contains("No hay"),"Audio advertised after failed delivery");
            job.Details=new Dictionary<string,object>();Call(form,"UpdateOpenButtons");Assert(((Label)Get(form,"finalValue")).Text=="—","Missing metric fabricated");
            string hash=Hash(input);job.Row.SubItems[1].Text="Pendiente";job.Settled=false;Call(form,"RemoveSelected");Assert(Hash(input)==hash,"Removing from queue touched original");
            var settings=new Dictionary<string,object>((Dictionary<string,object>)Get(form,"settings"));settings["threshold_db"]=-47;settings["margin"]=.25m;settings["audio_track"]=1;settings["threads"]=3;settings["preset"]="slow";settings["aac_bitrate"]="320k";settings["unknown_future_option"]="preserved";
            using(var editor=new SettingsForm(settings)) {
                editor.ShowInTaskbar=false;editor.WindowState=FormWindowState.Minimized;editor.Show();Application.DoEvents();editor.AcceptButton.PerformClick();
                Assert(editor.Result!=null,"Settings save failed");
                foreach(var key in new[]{"threshold_db","margin","audio_track","threads"})Assert(Convert.ToDecimal(editor.Result[key])==Convert.ToDecimal(settings[key]),"Setting changed silently: "+key);
                foreach(var key in new[]{"preset","aac_bitrate","unknown_future_option"})Assert(Convert.ToString(editor.Result[key])==Convert.ToString(settings[key]),"Setting lost: "+key);
            }
            using(var editor=new SettingsForm(settings)){editor.ShowInTaskbar=false;editor.WindowState=FormWindowState.Minimized;editor.Show();Application.DoEvents();editor.CancelButton.PerformClick();Assert(editor.Result==null,"Cancel saved settings");}
            form.WindowState=FormWindowState.Normal;form.Size=form.MinimumSize;form.PerformLayout();Application.DoEvents();CheckButtons(form);
            form.Scale(new SizeF(1.5f,1.5f));form.PerformLayout();Application.DoEvents();CheckButtons(form);
            form.Close();
        }
        Console.WriteLine("PASS UX bindings: partial/error, exact metrics, import validation, settings roundtrip, minimum/scaled layout");
        Ux002Contracts(input);
    }
    static void Ux002Contracts(string input){
        string destination=Path.Combine(Program.Root,"ux002-results"),resolved,error;Directory.CreateDirectory(destination);
        Assert(OutputDestination.TryResolve("",out resolved,out error)&&resolved=="","Empty output must retain original-folder mode");
        Assert(OutputDestination.TryResolve("\""+destination+"\"",out resolved,out error)&&resolved==destination,"Pasted quoted folder rejected");
        foreach(string invalid in new[]{"relative", "D:relative", "\\relative",Path.Combine(destination,"missing"),input,"bad?path"})
            Assert(!OutputDestination.TryResolve(invalid,out resolved,out error)&&error.Length>0,"Invalid folder accepted: "+invalid);
        using(var form=Form(destination,input)){
            var list=(ListView)Get(form,"queue");var job=Jobs(form).Last();var output=(TextBox)Get(form,"output");
            Assert(!output.ReadOnly,"Output path still read-only");Call(form,"ApplyDestination");
            output.Text=Path.Combine(destination,"missing");
            Assert(!(bool)Call(form,"ApplyDestination"),"Invalid destination applied");
            Assert(!((Button)Get(form,"start")).Enabled,"Invalid destination permits processing");
            Assert(Program.S((Dictionary<string,object>)Get(form,"settings"),"output_parent")==destination,"Invalid edit replaced saved preference");
            Finish(Start(form));Assert(!(bool)Get(form,"running"),"Invalid path started a worker");
            output.Text=destination;Call(form,"ApplyDestination");
            job.Completed=true;job.Settled=true;job.Row.SubItems[1].Text="Terminado";
            Set(form,"activeJob",job);((List<Job>)Get(form,"processingBatch")).Add(job);Call(form,"UpdateOpenButtons");
            Assert(((ProgressBar)Get(form,"queueProgress")).Value==100,"Confirmed batch not represented as complete");
            Call(form,"AddFiles",new object[]{new[]{input}});
            Assert(((ProgressBar)Get(form,"progress")).Value==0&&((ProgressBar)Get(form,"queueProgress")).Value==0,"Adding new pending work left 100 percent");
            var pending=Jobs(form).Last();Set(form,"running",true);Set(form,"activeJob",pending);Set(form,"activePercent",100);pending.Row.SubItems[1].Text="Procesando";((List<Job>)Get(form,"processingBatch")).Add(pending);Call(form,"RefreshProgress");
            Assert(((ProgressBar)Get(form,"progress")).Value<100&&((ProgressBar)Get(form,"queueProgress")).Value<100,"Unsettled work displayed as complete");
            Set(form,"running",false);pending.Row.SubItems[1].Text="Pendiente";
            list.SelectedItems.Clear();job.Row.Selected=true;job.Completed=false;job.Partial=true;job.PrimaryAvailable=true;job.Row.SubItems[1].Text="Entrega parcial";Call(form,"UpdateOpenButtons");
            form.WindowState=FormWindowState.Normal;form.Size=form.MinimumSize;Application.DoEvents();
            CheckNotice(form);CheckColumns(form);CheckButtons(form);
            for(int i=0;i<2;i++){form.WindowState=FormWindowState.Maximized;Application.DoEvents();CheckColumns(form);form.WindowState=FormWindowState.Normal;Application.DoEvents();CheckColumns(form);}
            job.Partial=false;job.Cancelled=true;job.Row.SubItems[1].Text="Cancelado";Call(form,"UpdateOpenButtons");Application.DoEvents();CheckNotice(form);
            form.Scale(new SizeF(1.5f,1.5f));Application.DoEvents();CheckNotice(form);CheckColumns(form);CheckButtons(form);
            form.Close();
        }
        using(var reopened=Form(destination))Assert(Program.S((Dictionary<string,object>)Get(reopened,"settings"),"output_parent")==destination,"Pasted destination did not persist");
        var settings=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Program.Root,"perfil_probado.json")));
        using(var editor=new SettingsForm(settings)){
            editor.ShowInTaskbar=false;editor.Show();Application.DoEvents();var box=(TextBox)Get(editor,"destination");
            box.Text=Path.Combine(destination,"missing");editor.AcceptButton.PerformClick();Assert(editor.Result==null&&!editor.IsDisposed,"Settings accepted invalid folder");
            box.Text=destination;editor.AcceptButton.PerformClick();Assert(Program.S(editor.Result,"output_parent")==destination,"Settings did not save pasted folder");
        }
        Console.WriteLine("PASS UX-002: wrapped notices, separate progress, safe editable destinations/persistence, repeatable columns and minimum/scaled layout");
    }
    static void CheckNotice(MainForm form){
        var notice=(Label)Get(form,"resultNotice");
        int needed=TextRenderer.MeasureText(notice.Text,notice.Font,new Size(Math.Max(1,notice.Width-notice.Padding.Horizontal),Int32.MaxValue),TextFormatFlags.WordBreak|TextFormatFlags.TextBoxControl).Height+notice.Padding.Vertical;
        TraceNotice(form,notice,needed);
        Assert(!notice.AutoEllipsis&&notice.Height>=needed-3,"Important notice text does not fit its wrapped height: "+notice.Height+" < "+needed);
        Assert(notice.Visible&&notice.Top>=0&&notice.Bottom<=notice.Parent.ClientSize.Height,"Terminal notice clipped or hidden behind a scroll viewport");
    }
    static void TraceNotice(MainForm form,Label notice,int needed){
        var screen=Screen.FromControl(form);
        Console.WriteLine("NOTICE environment interactive={0} dpi={1} screen={2} work={3} state={4} bounds={5} client={6} minimum={7} needed={8}",Environment.UserInteractive,form.DeviceDpi,screen.Bounds,screen.WorkingArea,form.WindowState,form.Bounds,form.ClientSize,form.MinimumSize,needed);
        for(Control control=notice;control!=null;control=control.Parent){
            Console.WriteLine("NOTICE control={0} bounds={1} client={2} visible={3} dock={4} padding={5} margin={6}",control.GetType().Name,control.Bounds,control.ClientRectangle,control.Visible,control.Dock,control.Padding,control.Margin);
            var scroll=control as ScrollableControl;
            if(scroll!=null)Console.WriteLine("NOTICE scroll auto={0} position={1} display={2} vertical={3} horizontal={4}",scroll.AutoScroll,scroll.AutoScrollPosition,scroll.DisplayRectangle,scroll.VerticalScroll.Visible,scroll.HorizontalScroll.Visible);
            var table=control as TableLayoutPanel;
            if(table!=null)Console.WriteLine("NOTICE rows={0}",String.Join(",",table.GetRowHeights()));
        }
    }
    static double Luminance(Color color){
        Func<byte,double> linear=value=>{double c=value/255.0;return c<=.04045?c/12.92:Math.Pow((c+.055)/1.055,2.4);};
        return .2126*linear(color.R)+.7152*linear(color.G)+.0722*linear(color.B);
    }
    static void Contrast(Color text,Color background,string name){double a=Luminance(text),b=Luminance(background);Assert((Math.Max(a,b)+.05)/(Math.Min(a,b)+.05)>=4.5,"Insufficient text contrast: "+name);}
    static void ThemeContracts(){
        Contrast(Visual.Ink,Visual.Surface,"body");Contrast(Visual.Muted,Visual.Surface,"secondary");Contrast(Visual.Muted,Visual.Field,"disabled");Contrast(Visual.OnAccent,Visual.Accent,"primary");Contrast(Visual.Warn,Visual.Surface,"partial/cancelled");Contrast(Visual.Bad,Visual.Surface,"error");
        using(var header=new BrandHeader{Size=new Size(500,80)})using(var bitmap=new Bitmap(500,80)){
            header.CreateControl();header.DrawToBitmap(bitmap,header.ClientRectangle);
            Assert(bitmap.GetPixel(499,79).ToArgb()==Visual.Canvas.ToArgb(),"Brand header reverted to the system light background");
            Assert(!header.TabStop&&header.AccessibleName.Contains("Pauselith"),"Brand keyboard/accessibility contract lost");
        }
        Console.WriteLine("PASS FINAL-001: text/disabled/status contrast, real rendered brand background and accessibility");
    }
    static void CheckColumns(MainForm form){
        var list=(ListView)Get(form,"queue");int total=list.Columns.Cast<ColumnHeader>().Sum(c=>c.Width);
        Assert(total<=list.ClientSize.Width,"Queue columns overflow after resize: "+total+" > "+list.ClientSize.Width);
        Assert(list.Columns[0].Width>80&&list.Columns[1].Width>80&&list.Columns[2].Width>35&&list.Columns[3].Width==0,"Essential columns collapsed or hidden folder expanded");
    }
    static void CheckButtons(MainForm form) {
        foreach(string name in new[]{"start","cancel","settingsButton","chooseOutput","openVideo","openFolder"}) {
            var button=(Button)Get(form,name);var position=Point.Empty;for(Control control=button;control!=form;control=control.Parent)position.Offset(control.Location);
            var rectangle=new Rectangle(position,button.ClientSize);
            Assert(rectangle.Width>20&&rectangle.Height>12&&rectangle.Left>=0&&rectangle.Top>=0&&rectangle.Right<=form.ClientSize.Width+2&&rectangle.Bottom<=form.ClientSize.Height+2,"Essential control outside client area: "+name+" "+rectangle);
        }
    }
    static string Hash(string path){using(var sha=System.Security.Cryptography.SHA256.Create())using(var stream=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(stream));}
}
