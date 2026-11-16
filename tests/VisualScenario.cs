// Explicit visual fault scenario using synthetic media and an already verified result.
// This harness is not part of the product build or distribution.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using KiyoCut;
class VisualScenario {
    const BindingFlags Flags=BindingFlags.Instance|BindingFlags.NonPublic;
    static object Get(object value,string name){return value.GetType().GetField(name,Flags).GetValue(value);}
    static void Call(object value,string name,params object[] args){value.GetType().GetMethod(name,Flags).Invoke(value,args);}
    [STAThread] static void Main(string[] args){
        if(args.Length!=3)throw new ArgumentException("source, verified Estado.json and isolated data directory required");
        Environment.SetEnvironmentVariable("KIYOCUT_DATA_DIR",Path.GetFullPath(args[2]));
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        using(var form=new MainForm(new[]{Path.GetFullPath(args[0])})){
            var timer=new Timer{Interval=250};timer.Tick+=(s,e)=>{
                var jobs=(List<Job>)Get(form,"jobs");if(jobs.Count==0)return;timer.Stop();timer.Dispose();
                var job=jobs.Last();var state=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(args[1]));
                state["event"]="partial";state["state"]="partial";state["primary_available"]=true;
                state["message"]="Simulación controlada de entrega parcial";
                state["stages"]=new Dictionary<string,object>{{"secondary_audio",new Dictionary<string,object>{{"status","fail"},{"reason","Visual fault scenario: secondary track unavailable"}}}};
                job.Output=Path.GetDirectoryName(Path.GetFullPath(args[1]));
                Call(form,"OnEvent",job,"KIYO:"+Program.Json.Serialize(state));
                job.Settled=true;job.Row.SubItems[1].Text="Entrega parcial";job.Row.ForeColor=Visual.Warn;job.Row.Selected=true;
                Call(form,"UpdateOpenButtons");form.Text="Pauselith · PRUEBA DIRIGIDA: entrega parcial · tamaño mínimo";
                form.Size=form.MinimumSize;form.PerformLayout();
            };
            form.Shown+=(s,e)=>timer.Start();Application.Run(form);
        }
    }
}
