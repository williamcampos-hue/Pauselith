using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows.Forms;

namespace KiyoCut {
static class Visual {
    internal static readonly Color Ink=SystemInformation.HighContrast?SystemColors.ControlText:Color.FromArgb(235,239,247);
    internal static readonly Color Muted=SystemInformation.HighContrast?SystemColors.ControlText:Color.FromArgb(163,175,194);
    internal static readonly Color Accent=SystemInformation.HighContrast?SystemColors.Highlight:Color.FromArgb(112,221,230);
    internal static readonly Color Canvas=SystemInformation.HighContrast?SystemColors.Control:Color.FromArgb(15,19,27);
    internal static readonly Color Surface=SystemInformation.HighContrast?SystemColors.Window:Color.FromArgb(25,31,42);
    internal static readonly Color Line=SystemInformation.HighContrast?SystemColors.ControlDark:Color.FromArgb(54,65,83);
    internal static readonly Color Field=SystemInformation.HighContrast?SystemColors.Window:Color.FromArgb(19,25,35);
    internal static readonly Color Selected=SystemInformation.HighContrast?SystemColors.Highlight:Color.FromArgb(39,65,78);
    internal static readonly Color Good=SystemInformation.HighContrast?Ink:Color.FromArgb(121,226,174);
    internal static readonly Color Warn=SystemInformation.HighContrast?Ink:Color.FromArgb(255,201,112);
    internal static readonly Color Bad=SystemInformation.HighContrast?Ink:Color.FromArgb(255,145,157);
    internal static readonly Color OnAccent=SystemInformation.HighContrast?SystemColors.HighlightText:Color.FromArgb(12,29,34);
    internal static Font Font(float size,bool bold=false){return new Font("Segoe UI",size,bold?FontStyle.Bold:FontStyle.Regular);}
    internal static Label Label(string text,float size=10,bool bold=false){return new Label{Text=text,Font=Font(size,bold),ForeColor=Ink,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft,AutoEllipsis=true,Margin=new Padding(0)};}
    internal static void Button(Button b,string text,bool primary=false){
        b.Text=text;b.AccessibleName=text.Replace("&","");b.Font=Font(10,true);b.FlatStyle=FlatStyle.Flat;b.FlatAppearance.BorderSize=primary?0:1;b.FlatAppearance.BorderColor=Line;
        b.BackColor=primary?Accent:Surface;b.ForeColor=primary?OnAccent:Ink;b.UseVisualStyleBackColor=false;b.Cursor=Cursors.Hand;b.Height=38;b.Margin=new Padding(0,0,8,0);
        b.EnabledChanged+=(s,e)=>{b.BackColor=b.Enabled?(primary?Accent:Surface):Field;b.ForeColor=b.Enabled?(primary?OnAccent:Ink):Muted;};
        b.FlatAppearance.MouseOverBackColor=primary?Color.FromArgb(148,235,242):Selected;b.FlatAppearance.MouseDownBackColor=primary?Color.FromArgb(83,193,204):Line;
        b.Paint+=(s,e)=>{
            if(!b.Enabled){using(var fill=new SolidBrush(b.BackColor))e.Graphics.FillRectangle(fill,b.ClientRectangle);using(var pen=new Pen(Line))e.Graphics.DrawRectangle(pen,0,0,b.Width-1,b.Height-1);TextRenderer.DrawText(e.Graphics,b.Text,b.Font,b.ClientRectangle,Muted,TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.HidePrefix);}
            if(b.Focused)ControlPaint.DrawFocusRectangle(e.Graphics,Rectangle.Inflate(b.ClientRectangle,-5,-5),b.ForeColor,b.BackColor);
        };
    }
    internal static void Inputs(Control root){
        foreach(Control c in root.Controls){
            if(c is TextBoxBase||c is NumericUpDown||c is ComboBox){c.BackColor=Field;c.ForeColor=Ink;}
            var combo=c as ComboBox;if(combo!=null)combo.FlatStyle=FlatStyle.Flat;
            var check=c as CheckBox;if(check!=null){check.UseVisualStyleBackColor=false;check.ForeColor=Ink;}
            Inputs(c);
        }
    }
    [System.Runtime.InteropServices.DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr window,int attribute,ref int value,int size);
    internal static void DarkTitle(Form form){form.HandleCreated+=(s,e)=>{if(SystemInformation.HighContrast)return;try{int value=1;DwmSetWindowAttribute(form.Handle,20,ref value,4);}catch(DllNotFoundException){}catch(EntryPointNotFoundException){}};}
    internal static TableLayoutPanel Table(int columns){var t=new FillTable{Dock=DockStyle.Fill,ColumnCount=columns,Margin=new Padding(0),BackColor=Color.Transparent};if(columns==1)t.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));return t;}
    internal static string Time(double? seconds){if(!seconds.HasValue)return "—";var t=TimeSpan.FromSeconds(Math.Max(0,seconds.Value));return t.TotalHours>=1?String.Format("{0}:{1:00}:{2:00}",(int)t.TotalHours,t.Minutes,t.Seconds):String.Format("{0}:{1:00}.{2}",(int)t.TotalMinutes,t.Seconds,t.Milliseconds/100);}
}
sealed class FillTable:TableLayoutPanel {
    protected override void OnControlAdded(ControlEventArgs e){if(RowStyles.Count==0)RowStyles.Add(new RowStyle(SizeType.Percent,100));base.OnControlAdded(e);}
}
sealed class Card:Panel {
    internal Card(){Dock=DockStyle.Fill;BackColor=Visual.Surface;Padding=new Padding(18);Margin=new Padding(0);SetStyle(ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw,true);}
    protected override void OnPaint(PaintEventArgs e){base.OnPaint(e);using(var p=new Pen(Visual.Line))e.Graphics.DrawRectangle(p,0,0,Math.Max(0,ClientSize.Width-1),Math.Max(0,ClientSize.Height-1));}
}
sealed class QueueList:ListView {
    internal QueueList(){DoubleBuffered=true;OwnerDraw=!SystemInformation.HighContrast;}
    protected override void OnDrawColumnHeader(DrawListViewColumnHeaderEventArgs e){
        if(!OwnerDraw){base.OnDrawColumnHeader(e);return;}
        using(var b=new SolidBrush(Visual.Field))e.Graphics.FillRectangle(b,e.Bounds);
        var box=e.Bounds;box.Inflate(-10,0);TextRenderer.DrawText(e.Graphics,e.Header.Text,Font,box,Visual.Muted,TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis);
    }
    protected override void OnDrawItem(DrawListViewItemEventArgs e){if(!OwnerDraw)base.OnDrawItem(e);}
    protected override void OnDrawSubItem(DrawListViewSubItemEventArgs e){
        if(!OwnerDraw){base.OnDrawSubItem(e);return;}
        Color bg=e.Item.Selected?Visual.Selected:(e.ItemIndex%2==0?Visual.Surface:Visual.Field);
        using(var b=new SolidBrush(bg))e.Graphics.FillRectangle(b,e.Bounds);
        var box=e.Bounds;box.Inflate(-10,0);
        Color fg=e.ColumnIndex==1?e.Item.ForeColor:Visual.Ink;
        TextRenderer.DrawText(e.Graphics,e.SubItem.Text,Font,box,fg,TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.NoPrefix);
        if(Focused&&e.Item.Focused&&e.ColumnIndex==0)ControlPaint.DrawFocusRectangle(e.Graphics,Rectangle.Inflate(e.Bounds,-2,-2),Visual.Accent,bg);
    }
}
sealed class TimelineProgress:ProgressBar {
    internal TimelineProgress(){SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);}
    protected override void OnPaint(PaintEventArgs e){
        e.Graphics.Clear(Visual.Field);int width=(int)(ClientSize.Width*(double)(Value-Minimum)/Math.Max(1,Maximum-Minimum));
        using(var b=new SolidBrush(Enabled?Visual.Accent:Visual.Muted))e.Graphics.FillRectangle(b,0,0,width,ClientSize.Height);
    }
}
sealed class SectionTabs:TabControl {
    internal SectionTabs(){SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);}
    protected override void OnPaint(PaintEventArgs e){e.Graphics.Clear(Visual.Canvas);}
}
// Abstract timeline mark: branding only, never a waveform or measurement of a file.
sealed class BrandHeader:Control {
    internal BrandHeader(){Dock=DockStyle.Fill;BackColor=Visual.Canvas;AccessibleName="Pauselith — Automatic Silence Remover";TabStop=false;SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw,true);}
    internal static void Mark(Graphics g,Rectangle box){
        var save=g.Save();g.TranslateTransform(box.Left,box.Top);g.ScaleTransform(box.Width/48f,box.Height/48f);
        using(var b=new SolidBrush(Visual.Accent))g.FillRectangle(b,0,0,48,48);
        using(var b=new SolidBrush(Visual.OnAccent)){g.FillRectangle(b,10,12,9,24);g.FillRectangle(b,24,12,14,9);g.FillRectangle(b,24,27,14,9);}
        g.Restore(save);
    }
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr icon);
    internal static Icon CreateIcon(){using(var bitmap=new Bitmap(48,48)){using(var g=Graphics.FromImage(bitmap))Mark(g,new Rectangle(0,0,48,48));var handle=bitmap.GetHicon();try{return (Icon)Icon.FromHandle(handle).Clone();}finally{DestroyIcon(handle);}}}
    protected override void OnPaint(PaintEventArgs e){
        base.OnPaint(e);float scale=DeviceDpi/96f;int icon=(int)(48*scale);int y=Math.Max(0,(Height-icon)/2);Mark(e.Graphics,new Rectangle(0,y,icon,icon));
        using(var title=Visual.Font(27,true))TextRenderer.DrawText(e.Graphics,"Pauselith",title,new Rectangle(icon+(int)(16*scale),y-5,Math.Max(1,Width-icon-16),45*(int)Math.Ceiling(scale)),Visual.Ink,TextFormatFlags.NoPadding|TextFormatFlags.EndEllipsis);
        using(var subtitle=Visual.Font(10))TextRenderer.DrawText(e.Graphics,"Automatic Silence Remover",subtitle,new Point(icon+(int)(18*scale),y+(int)(35*scale)),Visual.Muted,TextFormatFlags.NoPadding);
    }
}
static class OutputDestination {
    internal static bool TryResolve(string text,out string path,out string error){
        path="";error="";text=(text??"").Trim();
        if(text.Length==0)return true;
        if(text.Length>1&&text[0]=='"'&&text[text.Length-1]=='"')text=text.Substring(1,text.Length-2);
        try {
            bool drive=text.Length>=3&&Char.IsLetter(text[0])&&text[1]==':'&&(text[2]=='\\'||text[2]=='/');
            bool unc=text.StartsWith("\\\\")&&!text.StartsWith("\\\\?\\")&&!text.StartsWith("\\\\.\\");
            if((!drive&&!unc)||text.IndexOfAny(Path.GetInvalidPathChars())>=0||text.IndexOfAny(new[]{'*','?'})>=0){error="Usa una ruta absoluta de carpeta válida.";return false;}
            path=Path.GetFullPath(text);
            if(!Directory.Exists(path)){error=File.Exists(path)?"El destino es un archivo, no una carpeta.":"La carpeta no existe o no es accesible.";path="";return false;}
            return true;
        }catch(ArgumentException){error="La ruta contiene caracteres no válidos.";}
        catch(NotSupportedException){error="El formato de la ruta no es válido.";}
        catch(PathTooLongException){error="La ruta es demasiado larga.";}
        catch(System.Security.SecurityException){error="No tienes permiso para acceder a la carpeta.";}
        return false;
    }
}
static class ResultView {
    internal static double? Number(Dictionary<string,object> data,string key){object value;double n;if(data!=null&&data.TryGetValue(key,out value)&&value!=null&&Double.TryParse(Convert.ToString(value,CultureInfo.InvariantCulture),NumberStyles.Float,CultureInfo.InvariantCulture,out n)&&!Double.IsNaN(n)&&!Double.IsInfinity(n)&&n>=0)return n;return null;}
    internal static string Tracks(Dictionary<string,object> data){
        if(data==null)return "Se comprobarán las pistas al procesar.";
        string state=Program.S(data,"state",Program.S(data,"event"));
        if(state=="error"||state=="cancelled"||(state=="partial"&&!Program.B(data,"primary_available")))return "No hay un audio final confirmado.";
        object raw;if(!data.TryGetValue("audio",out raw))return "Se comprobarán las pistas al procesar.";
        var audio=raw as Dictionary<string,object>;if(audio==null)return "Información de audio no disponible.";
        object stagesRaw;var stages=data.TryGetValue("stages",out stagesRaw)?stagesRaw as Dictionary<string,object>:null;
        object secondaryRaw;var secondary=stages!=null&&stages.TryGetValue("secondary_audio",out secondaryRaw)?secondaryRaw as Dictionary<string,object>:null;
        if(secondary!=null&&Program.S(secondary,"status")=="fail")return "Advertencia: faltan pistas adicionales.";
        object count;return audio.TryGetValue("preserved_audio_tracks",out count)?Convert.ToString(count)+" pista(s) de audio en el vídeo final.":"Información de audio no disponible.";
    }
    internal static string Notice(Job job){
        if(job==null)return "Selecciona un vídeo de la cola para ver su resultado.";
        if(job.Partial)return job.PrimaryAvailable?"Entrega parcial. Puedes abrir el vídeo principal, pero faltan componentes o verificaciones. Consulta el registro.":"Entrega parcial sin un vídeo principal confirmado. Consulta el registro antes de usar los archivos.";
        if(job.Cancelled)return "Cancelación confirmada. Para repetir este vídeo, añádelo de nuevo. Los pendientes siguen en la cola.";
        if(job.Row.SubItems[1].Text=="Error"&&job.Error.StartsWith("Formato no compatible"))return job.Error;
        if(job.Row.SubItems[1].Text=="Error")return job.Recovered?"Trabajo recuperado tras una interrupción. No hay una entrega completa confirmada. Puedes añadir el original de nuevo.":"No se pudo procesar este archivo. Abre el registro para ver la causa y los detalles.";
        if(job.Completed)return job.Recovered?"Resultado verificado y recuperado tras una interrupción.":"Vídeo verificado y listo para continuar tu edición.";
        return "El resultado aparecerá aquí cuando termine la verificación.";
    }
}
partial class MainForm {
    readonly Label emptyQueue=Visual.Label("Tu cola está vacía\r\nAñade vídeos o arrástralos aquí.",12);
    readonly Label resultName=Visual.Label("Ningún vídeo seleccionado",13,true),resultState=Visual.Label("Sin resultado",10,true),resultNotice=Visual.Label("",10),tracksLabel=Visual.Label("",9);
    readonly Label originalValue=Visual.Label("—",20,true),finalValue=Visual.Label("—",20,true),removedValue=Visual.Label("—",20,true),cutsValue=Visual.Label("—",20,true);
    readonly Label profileLabel=Visual.Label("",10,true),sourceLabel=Visual.Label("",9);
    readonly Label destinationCaption=Visual.Label("Destino · junto a cada original",9,true);
    readonly Label queueTitle=Visual.Label("Cola de vídeos",12,true);
    readonly Label destinationError=Visual.Label("",8),currentProgressLabel=Visual.Label("Archivo · en espera",8),queueProgressLabel=Visual.Label("Cola · sin pendientes",8);
    readonly ProgressBar queueProgress=new TimelineProgress();
    readonly TextBox resultPath=new TextBox();
    readonly Button addButton=new Button(),removeButton=new Button(),clearButton=new Button();
    readonly LinkLabel logToggle=new LinkLabel();
    readonly ToolTip tips=new ToolTip{AutoPopDelay=12000};
    TableLayoutPanel mainLayout;
    bool logExpanded;
    bool resizingColumns;
    void BuildInterface(){
        Text="Pauselith · Automatic Silence Remover · 0.9.0-rc.1";Icon=BrandHeader.CreateIcon();FormClosed+=(s,e)=>Icon.Dispose();Visual.DarkTitle(this);
        AutoScaleDimensions=new SizeF(96,96);AutoScaleMode=AutoScaleMode.Dpi;Font=Visual.Font(10);BackColor=Visual.Canvas;ForeColor=Visual.Ink;
        ClientSize=new Size(1220,830);MinimumSize=new Size(1030,790);StartPosition=FormStartPosition.CenterScreen;KeyPreview=true;
        mainLayout=Visual.Table(1);mainLayout.Padding=new Padding(24,16,24,14);mainLayout.RowCount=5;
        foreach(var r in new[]{new RowStyle(SizeType.Absolute,80),new RowStyle(SizeType.Percent,100),new RowStyle(SizeType.Absolute,172),new RowStyle(SizeType.Absolute,0),new RowStyle(SizeType.Absolute,28)})mainLayout.RowStyles.Add(r);
        Controls.Add(mainLayout);
        var header=Visual.Table(2);header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));header.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,160));
        header.Controls.Add(new BrandHeader(),0,0);
        var local=Visual.Label("FIRST PASS\r\nLOCAL · SIN CUENTAS",9,true);local.ForeColor=Visual.Accent;local.TextAlign=ContentAlignment.MiddleRight;header.Controls.Add(local,1,0);mainLayout.Controls.Add(header,0,0);
        var workspace=Visual.Table(2);workspace.Margin=new Padding(0,0,0,16);workspace.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,67));workspace.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,33));mainLayout.Controls.Add(workspace,0,1);
        var left=Visual.Table(1);left.Margin=new Padding(0,0,16,0);left.RowStyles.Add(new RowStyle(SizeType.Absolute,128));left.RowStyles.Add(new RowStyle(SizeType.Percent,100));workspace.Controls.Add(left,0,0);
        var drop=new Card{BackColor=Visual.Field,Margin=new Padding(0,0,0,16)};var import=Visual.Table(2);import.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));import.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,160));
        var importText=Visual.Table(1);importText.RowStyles.Add(new RowStyle(SizeType.Percent,55));importText.RowStyles.Add(new RowStyle(SizeType.Percent,45));
        var title=Visual.Label("01  /  Importa tu grabación",14,true);importText.Controls.Add(title,0,0);
        var formats=Visual.Label("Arrastra vídeos aquí · MP4, MKV, MOV, WEBM…",9);formats.ForeColor=Visual.Muted;importText.Controls.Add(formats,0,1);import.Controls.Add(importText,0,0);
        Visual.Button(addButton,"&Añadir vídeos",true);addButton.Dock=DockStyle.Fill;addButton.Margin=new Padding(12,12,0,12);addButton.Click+=(s,e)=>AddDialog();import.Controls.Add(addButton,1,0);drop.Controls.Add(import);
        foreach(var control in new Control[]{drop,import,importText,title,formats})EnableDrop(control);EnableDrop(this);left.Controls.Add(drop,0,0);
        var queueCard=new Card{Padding=new Padding(16,12,16,12)};var queueLayout=Visual.Table(1);queueLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,40));queueLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));queueLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,25));queueCard.Controls.Add(queueLayout);left.Controls.Add(queueCard,0,1);
        var queueHead=Visual.Table(2);queueHead.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));queueHead.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,226));queueHead.Controls.Add(queueTitle,0,0);
        var queueActions=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false,Margin=new Padding(0)};
        Visual.Button(removeButton,"Retirar",false);removeButton.Width=86;removeButton.Height=30;removeButton.Click+=(s,e)=>RemoveSelected();queueActions.Controls.Add(removeButton);
        Visual.Button(clearButton,"Limpiar lista",false);clearButton.Width=120;clearButton.Height=30;clearButton.Click+=(s,e)=>ClearFinished();queueActions.Controls.Add(clearButton);queueHead.Controls.Add(queueActions,1,0);queueLayout.Controls.Add(queueHead,0,0);
        var queueArea=new Panel{Dock=DockStyle.Fill,Margin=new Padding(0)};
        queue.Dock=DockStyle.Fill;queue.BorderStyle=BorderStyle.None;queue.View=View.Details;queue.FullRowSelect=true;queue.HideSelection=false;queue.MultiSelect=true;queue.ShowItemToolTips=true;queue.BackColor=Visual.Surface;queue.ForeColor=Visual.Ink;queue.Font=Visual.Font(10);
        queue.Columns.Add("Vídeo",310);queue.Columns.Add("Estado",160);queue.Columns.Add("Final",82);queue.Columns.Add("Carpeta",0);
        var spacing=new ImageList{ImageSize=new Size(1,36),ColorDepth=ColorDepth.Depth32Bit};spacing.Images.Add(new Bitmap(1,36));queue.SmallImageList=spacing;FormClosed+=(s,e)=>spacing.Dispose();
        queue.SelectedIndexChanged+=(s,e)=>UpdateOpenButtons();queue.DoubleClick+=(s,e)=>OpenSelected(false);queue.Resize+=(s,e)=>ResizeQueueColumns();EnableDrop(queue);
        emptyQueue.TextAlign=ContentAlignment.MiddleCenter;emptyQueue.BackColor=Visual.Surface;emptyQueue.ForeColor=Visual.Muted;EnableDrop(emptyQueue);queueArea.Controls.Add(queue);queueArea.Controls.Add(emptyQueue);queueLayout.Controls.Add(queueArea,0,1);
        var safety=Visual.Label("Retirar o limpiar la lista conserva los archivos originales.",9);safety.ForeColor=Visual.Muted;queueLayout.Controls.Add(safety,0,2);
        workspace.Controls.Add(BuildResults(),1,0);
        var processing=new Card{Padding=new Padding(16,12,16,12)};processing.Margin=new Padding(0);mainLayout.Controls.Add(processing,0,2);
        var processLayout=Visual.Table(2);processLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));processLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,210));processing.Controls.Add(processLayout);
        var context=Visual.Table(1);context.Margin=new Padding(0,0,18,0);foreach(int h in new[]{64,18,23,38})context.RowStyles.Add(new RowStyle(SizeType.Absolute,h));processLayout.Controls.Add(context,0,0);
        var options=Visual.Table(2);options.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,43));options.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,57));
        var profile=Visual.Table(2);profile.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));profile.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,118));profile.RowStyles.Add(new RowStyle(SizeType.Absolute,25));profile.RowStyles.Add(new RowStyle(SizeType.Absolute,28));profile.Controls.Add(profileLabel,0,0);profile.Controls.Add(sourceLabel,0,1);
        Visual.Button(settingsButton,"Con&figurar");settingsButton.Dock=DockStyle.Fill;settingsButton.Font=Visual.Font(9,true);settingsButton.Margin=new Padding(4,8,14,8);profile.Controls.Add(settingsButton,1,0);profile.SetRowSpan(settingsButton,2);settingsButton.Click+=(s,e)=>EditSettings();options.Controls.Add(profile,0,0);
        var destination=Visual.Table(3);destination.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));destination.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,70));destination.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,66));destination.RowStyles.Add(new RowStyle(SizeType.Absolute,24));destination.RowStyles.Add(new RowStyle(SizeType.Absolute,30));
        destination.Controls.Add(destinationCaption,0,0);destination.SetColumnSpan(destination.GetControlFromPosition(0,0),3);
        output.BorderStyle=BorderStyle.FixedSingle;output.BackColor=Visual.Surface;output.Dock=DockStyle.Fill;output.Text=Program.S(settings,"output_parent");output.TextChanged+=(s,e)=>{destinationCaption.Text=String.IsNullOrWhiteSpace(output.Text)?"Destino · junto a cada original":"Guardar resultados en";ValidateDestination();RefreshQueue();};destinationCaption.Text=String.IsNullOrEmpty(output.Text)?"Destino · junto a cada original":"Guardar resultados en";output.AccessibleName="Carpeta de salida; pega una ruta o deja vacío para usar el original";output.Margin=new Padding(0,0,6,0);output.Leave+=(s,e)=>{if(!running)ApplyDestination();};output.KeyDown+=(s,e)=>{if(e.KeyCode==Keys.Enter){e.SuppressKeyPress=true;ApplyDestination();}};destination.Controls.Add(output,0,1);
        Visual.Button(chooseOutput,"Elegir");chooseOutput.Dock=DockStyle.Fill;chooseOutput.Font=Visual.Font(9);chooseOutput.Margin=new Padding(0,0,6,0);chooseOutput.Click+=(s,e)=>ChooseOutput();destination.Controls.Add(chooseOutput,1,1);
        Visual.Button(resetOutput,"Original");resetOutput.Dock=DockStyle.Fill;resetOutput.Font=Visual.Font(9);resetOutput.Margin=new Padding(0);resetOutput.Click+=(s,e)=>{output.Text="";settings["output_parent"]="";SaveSettings();phase.Text="Cada vídeo se guardará junto al original, en su propia carpeta.";};destination.Controls.Add(resetOutput,2,1);options.Controls.Add(destination,1,0);context.Controls.Add(options,0,0);
        destinationError.ForeColor=Visual.Bad;destinationError.AccessibleName="Validación de carpeta de salida";context.Controls.Add(destinationError,0,1);ValidateDestination();
        phase.Text="Añade vídeos y pulsa Procesar vídeos.";phase.Dock=DockStyle.Fill;phase.AutoEllipsis=true;phase.Font=Visual.Font(9);phase.ForeColor=Visual.Muted;context.Controls.Add(phase,0,2);
        var meters=Visual.Table(2);meters.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));meters.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));meters.RowStyles.Add(new RowStyle(SizeType.Absolute,22));meters.RowStyles.Add(new RowStyle(SizeType.Absolute,10));meters.Controls.Add(currentProgressLabel,0,0);meters.Controls.Add(queueProgressLabel,1,0);
        progress.AccessibleName="Progreso del archivo actual";queueProgress.AccessibleName="Progreso global de la cola";foreach(var bar in new[]{progress,queueProgress}){bar.Dock=DockStyle.Fill;bar.Margin=new Padding(0,0,12,0);bar.Minimum=0;bar.Maximum=100;}meters.Controls.Add(progress,0,1);meters.Controls.Add(queueProgress,1,1);context.Controls.Add(meters,0,3);
        var actions=Visual.Table(1);actions.RowStyles.Add(new RowStyle(SizeType.Absolute,44));actions.RowStyles.Add(new RowStyle(SizeType.Absolute,32));actions.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        Visual.Button(start,"&Procesar vídeos",true);start.Dock=DockStyle.Fill;start.Margin=new Padding(0,0,0,4);start.Click+=async(s,e)=>await ProcessQueue();actions.Controls.Add(start,0,0);
        Visual.Button(cancel,"Cancelar cola");cancel.Dock=DockStyle.Fill;cancel.Margin=new Padding(0);cancel.Enabled=false;cancel.Click+=(s,e)=>CancelQueue();actions.Controls.Add(cancel,0,1);
        counter.Dock=DockStyle.Fill;counter.TextAlign=ContentAlignment.MiddleCenter;counter.Font=Visual.Font(8);counter.ForeColor=Visual.Muted;counter.AutoEllipsis=true;actions.Controls.Add(counter,0,2);processLayout.Controls.Add(actions,1,0);
        logbox.Multiline=true;logbox.ReadOnly=true;logbox.ScrollBars=ScrollBars.Vertical;logbox.Dock=DockStyle.Fill;logbox.BackColor=Visual.Surface;logbox.ForeColor=Visual.Ink;logbox.BorderStyle=BorderStyle.FixedSingle;logbox.Font=Visual.Font(9);logbox.Visible=false;logbox.AccessibleName="Detalles del procesamiento";mainLayout.Controls.Add(logbox,0,3);
        var footer=Visual.Table(2);footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,178));var hint=Visual.Label("Ctrl+O  Añadir vídeos      Ctrl+Entrar  Procesar      Supr  Retirar",8);hint.ForeColor=Visual.Muted;footer.Controls.Add(hint,0,0);
        logToggle.Text="Mostrar detalles  ·  Ctrl+L";logToggle.LinkColor=Visual.Muted;logToggle.ActiveLinkColor=Visual.Accent;logToggle.Dock=DockStyle.Fill;logToggle.TextAlign=ContentAlignment.MiddleRight;logToggle.LinkClicked+=(s,e)=>ToggleLog();footer.Controls.Add(logToggle,1,0);mainLayout.Controls.Add(footer,0,4);
        tips.SetToolTip(output,"Pega una ruta de carpeta existente y pulsa Entrar. Vacío: junto a cada vídeo original.");tips.SetToolTip(resetOutput,"Guardar junto a cada original en una carpeta nueva");tips.SetToolTip(removeButton,"Retira solo los vídeos que no se están procesando. No borra archivos.");tips.SetToolTip(clearButton,"Retira de la lista los resultados y errores. No borra archivos.");
        KeyDown+=async(s,e)=>{if(!Enabled||OwnedForms.Any(f=>f.Visible))return;if(e.Control&&e.KeyCode==Keys.O){e.SuppressKeyPress=true;AddDialog();}else if(e.Control&&e.KeyCode==Keys.Enter){e.SuppressKeyPress=true;await ProcessQueue();}else if(e.Control&&e.KeyCode==Keys.L){e.SuppressKeyPress=true;ToggleLog();}else if(e.KeyCode==Keys.Delete&&queue.Focused){e.SuppressKeyPress=true;RemoveSelected();}else if(e.KeyCode==Keys.Escape&&running){e.SuppressKeyPress=true;CancelQueue();}};
        Visual.Inputs(this);RefreshProfile();RefreshQueue();ResizeQueueColumns();
    }
    Control BuildResults(){
        var card=new Card{Padding=new Padding(16)};var layout=Visual.Table(1);layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,100));card.Controls.Add(layout);
        var scroll=new Panel{Dock=DockStyle.Fill,AutoScroll=true,Margin=new Padding(0)};layout.Controls.Add(scroll,0,0);
        var content=Visual.Table(1);content.Dock=DockStyle.Top;content.AutoSize=true;content.AutoSizeMode=AutoSizeMode.GrowAndShrink;scroll.Controls.Add(content);
        foreach(var h in new[]{22,36,24,104,32})content.RowStyles.Add(new RowStyle(SizeType.Absolute,h));
        var caption=Visual.Label("03  /  RESULTADO SELECCIONADO",8,true);caption.ForeColor=Visual.Accent;content.Controls.Add(caption,0,0);content.Controls.Add(resultName,0,1);content.Controls.Add(resultState,0,2);
        finalValue.ForeColor=Visual.Accent;removedValue.ForeColor=Visual.Good;cutsValue.ForeColor=Visual.Accent;
        var metrics=Visual.Table(2);metrics.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));metrics.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));metrics.RowStyles.Add(new RowStyle(SizeType.Percent,50));metrics.RowStyles.Add(new RowStyle(SizeType.Percent,50));
        metrics.Controls.Add(Metric("Original",originalValue),0,0);metrics.Controls.Add(Metric("Resultado",finalValue),1,0);metrics.Controls.Add(Metric("Tiempo eliminado",removedValue),0,1);metrics.Controls.Add(Metric("Cortes de silencio",cutsValue),1,1);content.Controls.Add(metrics,0,3);
        tracksLabel.ForeColor=Visual.Muted;content.Controls.Add(tracksLabel,0,4);resultNotice.TextAlign=ContentAlignment.TopLeft;resultNotice.Padding=new Padding(8);resultNotice.AutoEllipsis=false;resultNotice.AutoSize=true;resultNotice.Dock=DockStyle.Top;resultNotice.BackColor=Visual.Canvas;resultNotice.Margin=new Padding(0,4,0,8);layout.Controls.Add(resultNotice,0,1);
        layout.SizeChanged+=(s,e)=>{int width=Math.Max(1,layout.ClientSize.Width);if(resultNotice.MaximumSize.Width!=width)resultNotice.MaximumSize=new Size(width,0);};
        var buttons=Visual.Table(2);buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));buttons.RowStyles.Add(new RowStyle(SizeType.Absolute,42));buttons.RowStyles.Add(new RowStyle(SizeType.Absolute,24));buttons.RowStyles.Add(new RowStyle(SizeType.Absolute,30));layout.Controls.Add(buttons,0,2);
        Visual.Button(openVideo,"Abrir &vídeo",true);openVideo.Dock=DockStyle.Fill;openVideo.Margin=new Padding(0,4,6,2);openVideo.Click+=(s,e)=>OpenSelected(true);buttons.Controls.Add(openVideo,0,0);
        Visual.Button(openFolder,"Ver &carpeta");openFolder.Dock=DockStyle.Fill;openFolder.Margin=new Padding(0,4,0,2);openFolder.Click+=(s,e)=>OpenSelected(false);buttons.Controls.Add(openFolder,1,0);
        resultPath.ReadOnly=true;resultPath.Dock=DockStyle.Fill;resultPath.BorderStyle=BorderStyle.None;resultPath.BackColor=Visual.Surface;resultPath.ForeColor=Visual.Muted;resultPath.Font=Visual.Font(8);resultPath.AccessibleName="Ruta del resultado";buttons.Controls.Add(resultPath,0,1);buttons.SetColumnSpan(resultPath,2);
        Visual.Button(openLog,"Abrir registro");openLog.Dock=DockStyle.Fill;openLog.Font=Visual.Font(9);openLog.Margin=new Padding(0);openLog.Click+=(s,e)=>{var j=Selected();if(j!=null)Program.Open(j.Log);};buttons.Controls.Add(openLog,0,2);buttons.SetColumnSpan(openLog,2);
        return card;
    }
    Control Metric(string caption,Label value){var panel=Visual.Table(1);panel.RowStyles.Add(new RowStyle(SizeType.Absolute,20));panel.RowStyles.Add(new RowStyle(SizeType.Percent,100));var label=Visual.Label(caption,9);label.ForeColor=Visual.Muted;panel.Controls.Add(label,0,0);panel.Controls.Add(value,0,1);return panel;}
    void ToggleLog(){logExpanded=!logExpanded;logbox.Visible=logExpanded;mainLayout.RowStyles[3].Height=logExpanded?108:0;logToggle.Text=(logExpanded?"Ocultar":"Mostrar")+" detalles  ·  Ctrl+L";if(logExpanded)logbox.SelectionStart=logbox.TextLength;}
    void ResizeQueueColumns(){
        if(resizingColumns||queue.Columns.Count<4)return;resizingColumns=true;queue.BeginUpdate();
        try{
            int width=Math.Max(0,queue.ClientSize.Width-4);
            int state=Math.Min(width,TextRenderer.MeasureText("Procesando 100 %",queue.Font).Width+16);
            int final=Math.Min(Math.Max(0,width-state),TextRenderer.MeasureText("0:00:00",queue.Font).Width+16);
            // Shrink first: intermediate widths must not create a native horizontal scrollbar.
            foreach(ColumnHeader column in queue.Columns)column.Width=0;
            queue.Columns[1].Width=state;queue.Columns[2].Width=final;queue.Columns[0].Width=Math.Max(0,width-state-final);
        }finally{queue.EndUpdate();resizingColumns=false;}
    }
    bool ValidateDestination(){string path,error;bool valid=OutputDestination.TryResolve(output.Text,out path,out error);destinationError.Text=valid?"":error;tips.SetToolTip(destinationError,error);return valid;}
    bool ApplyDestination(){
        string path,error;if(!OutputDestination.TryResolve(output.Text,out path,out error)){ValidateDestination();return false;}
        output.Text=path;if(Program.S(settings,"output_parent")!=path){settings["output_parent"]=path;SaveSettings();}ValidateDestination();return true;
    }
    void RefreshProgress(){
        int pending=jobs.Count(j=>j.Row.SubItems[1].Text=="Pendiente");
        var batch=processingBatch.Where(j=>jobs.Contains(j)).ToArray();int settled=batch.Count(j=>j.Settled);
        bool active=running&&activeJob!=null&&!activeJob.Settled;
        if(active){progress.Value=Math.Min(99,activePercent);currentProgressLabel.Text="Archivo · "+progress.Value+" % · "+Path.GetFileName(activeJob.Input);}
        else{progress.Value=!running&&pending==0&&activeJob!=null&&activeJob.Settled&&!activeJob.Cancelled&&(activeJob.Completed||activeJob.Partial)?100:0;currentProgressLabel.Text="Archivo · "+(pending>0?"en espera":activeJob==null?"sin actividad":activeJob.Row.SubItems[1].Text);}
        if(!running&&pending>0){queueProgress.Value=0;queueProgressLabel.Text="Cola · "+pending+" pendientes";}
        else if(!running&&cancelRequested){queueProgress.Value=0;queueProgressLabel.Text="Cola · cancelada";}
        else{queueProgress.Value=batch.Length==0?0:Math.Min(active||settled<batch.Length?99:100,(int)(100.0*(settled+(active?progress.Value/100.0:0))/batch.Length));queueProgressLabel.Text=String.Format("Cola · {0} % · {1}/{2} revisados",queueProgress.Value,settled,batch.Length);}
        progress.Invalidate();queueProgress.Invalidate();tips.SetToolTip(currentProgressLabel,currentProgressLabel.Text);tips.SetToolTip(queueProgressLabel,queueProgressLabel.Text);
    }
    void RefreshProfile(){
        var original=Program.Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Program.Root,"perfil_probado.json"),System.Text.Encoding.UTF8));
        bool same=original.Where(p=>p.Key!="output_parent").All(p=>settings.ContainsKey(p.Key)&&Convert.ToString(settings[p.Key],CultureInfo.InvariantCulture)==Convert.ToString(p.Value,CultureInfo.InvariantCulture));
        profileLabel.Text=same?"Perfil aprobado":"Ajustes personalizados";sourceLabel.Text="Audio · Pista "+Convert.ToString(settings["audio_track"])+(Convert.ToInt32(settings["audio_track"])==2?" / única disponible":"");
    }
    void RefreshQueue(){if(!running)start.Enabled=(recoveryTask==null||recoveryTask.IsCompleted)&&jobs.Any(j=>j.Row.SubItems[1].Text=="Pendiente")&&ValidateDestination();emptyQueue.Visible=jobs.Count==0;emptyQueue.Dock=DockStyle.Fill;if(emptyQueue.Visible)emptyQueue.BringToFront();queueTitle.Text="02  /  Cola de vídeos"+(jobs.Count>0?"  ·  "+jobs.Count:"");counter.Text=String.Format("{0} pendientes · {1} listos",jobs.Count(j=>j.Row.SubItems[1].Text=="Pendiente"),jobs.Count(j=>j.Completed));removeButton.Enabled=Selected()!=null&&!Selected().Row.SubItems[1].Text.StartsWith("Procesando");clearButton.Enabled=jobs.Any(j=>j.Settled||j.Completed||j.Partial||j.Cancelled||j.Row.SubItems[1].Text=="Error");RefreshProgress();}
    void RefreshResult(){
        if(resultName==null)return;var job=Selected();resultName.Text=job==null?"Ningún vídeo seleccionado":Path.GetFileName(job.Input);tips.SetToolTip(resultName,job==null?"":job.Input);
        resultState.Text=job==null?"Sin resultado":job.Row.SubItems[1].Text;resultState.ForeColor=job==null?Visual.Muted:job.Completed?Visual.Good:job.Partial||job.Cancelled?Visual.Warn:job.Row.SubItems[1].Text=="Error"?Visual.Bad:Visual.Accent;
        var data=job==null?null:job.Details;bool measured=job!=null&&job.Settled&&(job.Completed||job.Partial);
        double? final=measured?ResultView.Number(data,"final_seconds"):null,removed=measured?ResultView.Number(data,"removed_seconds"):null;
        originalValue.Text=Visual.Time(final.HasValue&&removed.HasValue?final+removed:null);finalValue.Text=Visual.Time(final);removedValue.Text=Visual.Time(removed);
        var cuts=measured?ResultView.Number(data,"removed_intervals"):null;cutsValue.Text=cuts.HasValue?cuts.Value.ToString("0",CultureInfo.CurrentCulture):"—";
        tracksLabel.Text=job==null?"Las pistas de audio se mantienen separadas.":job.Settled&&job.Row.SubItems[1].Text=="Error"&&!job.PrimaryAvailable?"No hay un audio final confirmado.":ResultView.Tracks(data);resultNotice.Text=ResultView.Notice(job);resultNotice.ForeColor=job!=null&&(job.Partial||job.Cancelled)?Visual.Warn:job!=null&&job.Row.SubItems[1].Text=="Error"?Visual.Bad:Visual.Muted;
        resultPath.Text=job==null?"":job.Output;tips.SetToolTip(resultPath,resultPath.Text);
    }
}
}
