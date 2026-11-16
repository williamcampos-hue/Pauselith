using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows.Forms;
namespace KiyoCut {
class SettingsForm:Form {
    internal Dictionary<string,object> Result;
    readonly Dictionary<string,NumericUpDown> numbers=new Dictionary<string,NumericUpDown>();
    readonly CheckBox clips=new CheckBox(),extras=new CheckBox();
    readonly ComboBox audio=new ComboBox(),preset=new ComboBox(),bitrate=new ComboBox();
    readonly TextBox destination=new TextBox();
    readonly Label profile=Visual.Label("",11,true);
    readonly Label destinationError=Visual.Label("",9);
    readonly Dictionary<string,object> original;
    bool loading;
    public SettingsForm(Dictionary<string,object> current){
        original=Program.Json.Deserialize<Dictionary<string,object>>(Program.Json.Serialize(current));
        Text="Pauselith · Configuración";Visual.DarkTitle(this);AutoScaleDimensions=new SizeF(96,96);AutoScaleMode=AutoScaleMode.Dpi;Font=Visual.Font(10);BackColor=Visual.Canvas;ForeColor=Visual.Ink;
        ClientSize=new Size(700,620);MinimumSize=new Size(660,540);StartPosition=FormStartPosition.CenterParent;MinimizeBox=false;MaximizeBox=false;ShowInTaskbar=false;
        var root=Visual.Table(1);root.Padding=new Padding(22);root.RowStyles.Add(new RowStyle(SizeType.Absolute,52));root.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.RowStyles.Add(new RowStyle(SizeType.Absolute,54));Controls.Add(root);
        root.Controls.Add(Visual.Label("Ajusta tu primera pasada",18,true),0,0);
        var tabArea=Visual.Table(1);tabArea.RowStyles.Add(new RowStyle(SizeType.Absolute,44));tabArea.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.Controls.Add(tabArea,0,1);
        var selectors=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false,Margin=new Padding(0)};
        var generalTab=new Button{Width=126};var advancedTab=new Button{Width=126};Visual.Button(generalTab,"General");Visual.Button(advancedTab,"Avanzado");selectors.Controls.Add(generalTab);selectors.Controls.Add(advancedTab);tabArea.Controls.Add(selectors,0,0);
        var tabs=new SectionTabs{Dock=DockStyle.Fill,Appearance=TabAppearance.FlatButtons,SizeMode=TabSizeMode.Fixed,ItemSize=new Size(1,1),Multiline=false,AccessibleName="Niveles de configuración · Ctrl+Tab"};tabArea.Controls.Add(tabs,0,1);
        var simple=new TabPage("General"){BackColor=Visual.Surface,Padding=new Padding(18),AutoScroll=true};var advanced=new TabPage("Avanzado"){BackColor=Visual.Surface,Padding=new Padding(18),AutoScroll=true};tabs.TabPages.Add(simple);tabs.TabPages.Add(advanced);
        Action selectTab=()=>{foreach(var button in new[]{generalTab,advancedTab}){bool selected=button==generalTab?tabs.SelectedIndex==0:tabs.SelectedIndex==1;button.BackColor=selected?Visual.Accent:Visual.Surface;button.ForeColor=selected?Visual.OnAccent:Visual.Ink;button.FlatAppearance.MouseOverBackColor=selected?Visual.Accent:Visual.Selected;button.FlatAppearance.MouseDownBackColor=selected?Visual.Accent:Visual.Line;}};
        generalTab.Click+=(s,e)=>{tabs.SelectedIndex=0;};advancedTab.Click+=(s,e)=>{tabs.SelectedIndex=1;};tabs.SelectedIndexChanged+=(s,e)=>selectTab();selectTab();
        Shown+=(s,e)=>selectTab();
        var general=Visual.Table(1);general.Dock=DockStyle.Top;general.AutoSize=true;foreach(int h in new[]{30,48,26,38,48,36,42,26,34,30})general.RowStyles.Add(new RowStyle(SizeType.Absolute,h));simple.Controls.Add(general);
        general.Controls.Add(profile,0,0);var note=Visual.Label("El perfil aprobado protege el comienzo y el final de las palabras. Los cambios se aplicarán a los próximos vídeos.",10);general.Controls.Add(note,0,1);
        general.Controls.Add(Visual.Label("Qué audio guía los cortes",10,true),0,2);audio.DropDownStyle=ComboBoxStyle.DropDownList;audio.Dock=DockStyle.Fill;audio.AccessibleName="Fuente de audio";for(int i=1;i<=16;i++)audio.Items.Add("Pista "+i+(i==2?" (o única disponible)":""));general.Controls.Add(audio,0,3);
        var sourceNote=Visual.Label("Elige la pista que contiene tu voz. Los formatos y el número real de pistas se comprueban al procesar; no se mezclan los audios.",9);sourceNote.ForeColor=Visual.Muted;general.Controls.Add(sourceNote,0,4);
        clips.Text="Crear también un archivo por cada segmento";clips.Dock=DockStyle.Fill;clips.AccessibleName=clips.Text;general.Controls.Add(clips,0,5);
        extras.Text="Conservar las demás pistas de audio por separado";extras.Dock=DockStyle.Fill;extras.AccessibleName=extras.Text;general.Controls.Add(extras,0,6);
        general.Controls.Add(Visual.Label("Carpeta de resultados (vacía: junto al original)",9,true),0,7);
        var folder=Visual.Table(2);folder.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));folder.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,88));destination.Dock=DockStyle.Fill;destination.AccessibleName="Destino de exportación; admite pegar una ruta";folder.Controls.Add(destination,0,0);
        var choose=new Button();Visual.Button(choose,"Elegir…");choose.Dock=DockStyle.Fill;choose.Margin=new Padding(8,0,0,0);choose.Click+=(s,e)=>{using(var d=new FolderBrowserDialog{Description="Dónde guardar los resultados",SelectedPath=destination.Text})if(d.ShowDialog(this)==DialogResult.OK)destination.Text=d.SelectedPath;};folder.Controls.Add(choose,1,0);general.Controls.Add(folder,0,8);
        destinationError.ForeColor=Visual.Bad;destinationError.AccessibleName="Error de carpeta de resultados";general.Controls.Add(destinationError,0,9);
        destination.TextChanged+=(s,e)=>{string path,error;OutputDestination.TryResolve(destination.Text,out path,out error);destinationError.Text=error;};
        var technical=Visual.Table(2);technical.Dock=DockStyle.Top;technical.AutoSize=true;technical.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,70));technical.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,30));advanced.Controls.Add(technical);
        AddNumber(technical,0,"Pista exacta de audio","audio_track",1,16,0,1);
        AddNumber(technical,1,"Umbral de silencio · dBFS","threshold_db",-90,-10,0,1);
        AddNumber(technical,2,"Silencio mínimo · segundos","min_silence",.1m,30,2,.05m);
        AddNumber(technical,3,"Margen de voz a cada lado · segundos","margin",.01m,3,2,.05m);
        AddNumber(technical,4,"Segmento mínimo · segundos","min_clip",.1m,30,2,.05m);
        AddNumber(technical,5,"Calidad H.264 · CRF (menor = más calidad)","crf",0,30,0,1);
        AddNumber(technical,6,"Hilos de procesamiento","threads",1,16,0,1);
        AddChoice(technical,7,"Preset H.264",preset,new[]{"medium","fast","slow"});AddChoice(technical,8,"Calidad de audio AAC",bitrate,new[]{"192k","256k","320k"});
        var technicalNote=Visual.Label("Más cortes: aumenta el umbral o reduce el silencio mínimo. El perfil aprobado no cambia hasta que pulses Guardar.",9);technicalNote.ForeColor=Visual.Muted;technical.RowStyles.Add(new RowStyle(SizeType.Absolute,58));technical.Controls.Add(technicalNote,0,9);technical.SetColumnSpan(technicalNote,2);
        var footer=Visual.Table(2);footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,228));root.Controls.Add(footer,0,2);
        var reset=new Button();Visual.Button(reset,"Restaurar perfil aprobado");reset.Anchor=AnchorStyles.Left;reset.AutoSize=true;reset.Height=36;reset.Click+=(s,e)=>LoadValues(Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Program.Root,"perfil_probado.json"),System.Text.Encoding.UTF8)),false);footer.Controls.Add(reset,0,0);
        var actions=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false,Padding=new Padding(0,10,0,0),Margin=new Padding(0)};
        var save=new Button{Width=112};Visual.Button(save,"&Guardar",true);save.Click+=(s,e)=>{
            string path,error;if(!OutputDestination.TryResolve(destination.Text,out path,out error)){destinationError.Text=error;tabs.SelectedTab=simple;destination.Focus();return;}
            Result=new Dictionary<string,object>(original);foreach(var p in numbers)Result[p.Key]=p.Value.Value;
            Result["individual_clips"]=clips.Checked;Result["preserve_other_audio"]=extras.Checked;Result["preset"]=Convert.ToString(preset.SelectedItem);Result["aac_bitrate"]=Convert.ToString(bitrate.SelectedItem);Result["output_parent"]=path;
            DialogResult=DialogResult.OK;Close();};actions.Controls.Add(save);
        var cancel=new Button{Width=106,DialogResult=DialogResult.Cancel};Visual.Button(cancel,"Cancelar");actions.Controls.Add(cancel);footer.Controls.Add(actions,1,0);AcceptButton=save;CancelButton=cancel;
        audio.SelectedIndexChanged+=(s,e)=>{if(!loading&&audio.SelectedIndex>=0){numbers["audio_track"].Value=audio.SelectedIndex+1;profile.Text="Cambios pendientes · Guarda para aplicarlos";}};
        numbers["audio_track"].ValueChanged+=(s,e)=>{if(!loading)audio.SelectedIndex=(int)numbers["audio_track"].Value-1;};
        foreach(var n in numbers.Values)n.ValueChanged+=(s,e)=>{if(!loading)profile.Text="Cambios pendientes · Guarda para aplicarlos";};
        Visual.Inputs(this);LoadValues(current,true);
    }
    void AddNumber(TableLayoutPanel table,int row,string label,string key,decimal min,decimal max,int decimals,decimal increment){
        table.RowStyles.Add(new RowStyle(SizeType.Absolute,42));table.Controls.Add(Visual.Label(label,10),0,row);
        var number=new NumericUpDown{Minimum=min,Maximum=max,DecimalPlaces=decimals,Increment=increment,Dock=DockStyle.Fill,Margin=new Padding(6,6,0,6),AccessibleName=label};numbers[key]=number;table.Controls.Add(number,1,row);
    }
    void AddChoice(TableLayoutPanel table,int row,string label,ComboBox combo,string[] values){table.RowStyles.Add(new RowStyle(SizeType.Absolute,42));table.Controls.Add(Visual.Label(label),0,row);combo.Items.AddRange(values);combo.DropDownStyle=ComboBoxStyle.DropDownList;combo.Dock=DockStyle.Fill;combo.Margin=new Padding(6);combo.AccessibleName=label;table.Controls.Add(combo,1,row);}
    void LoadValues(Dictionary<string,object> values,bool includeDestination){
        loading=true;foreach(var p in numbers)p.Value.Value=Math.Max(p.Value.Minimum,Math.Min(p.Value.Maximum,Convert.ToDecimal(values[p.Key])));
        audio.SelectedIndex=(int)numbers["audio_track"].Value-1;clips.Checked=Program.B(values,"individual_clips",true);extras.Checked=Program.B(values,"preserve_other_audio",true);
        preset.SelectedItem=Program.S(values,"preset","medium");bitrate.SelectedItem=Program.S(values,"aac_bitrate","256k");if(includeDestination)destination.Text=Program.S(values,"output_parent");
        profile.Text=includeDestination?"Configuración actual":"Perfil aprobado restaurado · Guarda para aplicarlo";loading=false;
    }
}
}
