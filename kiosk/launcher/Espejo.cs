// Panel del evento: one window to start/stop the mirror, find the photos, back them up and print them again.
// Built with the C# compiler that ships with Windows (see kiosk/build-launcher.ps1), so no extra tools are needed.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Windows.Forms;

class Espejo : Form
{
    static readonly string Root = FindRoot();
    static readonly string Photos = Path.Combine(Root, "media", "processed_full");
    static readonly string Originals = Path.Combine(Root, "media", "camera_original");
    static readonly string BackupRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Fotos Espejo");

    Label status = new Label();
    Label info = new Label();
    Timer timer = new Timer();
    int tick = 0;

    static string FindRoot()
    {
        var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
        while (dir != null && !Directory.Exists(Path.Combine(dir.FullName, "kiosk"))) dir = dir.Parent;
        return dir != null ? dir.FullName : AppDomain.CurrentDomain.BaseDirectory;
    }

    Espejo()
    {
        Text = "Espejo magico - Panel del evento";
        ClientSize = new Size(460, 650);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        Font = new Font("Segoe UI", 11f);
        BackColor = Color.FromArgb(20, 20, 30);
        ForeColor = Color.White;

        status.SetBounds(20, 14, 420, 30);
        status.Font = new Font("Segoe UI", 13f, FontStyle.Bold);
        Controls.Add(status);

        AddButton(0, "Iniciar espejo", Color.FromArgb(46, 125, 50), StartMirror);
        AddButton(1, "SACAR FOTO   (tecla F en la pantalla)", Color.FromArgb(160, 110, 20), delegate { TakePhoto("image/0"); });
        AddButton(2, "SACAR TIRA   (tecla T en la pantalla)", Color.FromArgb(160, 110, 20), delegate { TakePhoto("collage/1"); });
        AddButton(3, "Abrir carpeta de fotos", Color.FromArgb(60, 60, 90), delegate { Open(Photos); });
        AddButton(4, "Imprimir fotos otra vez...", Color.FromArgb(60, 60, 90), PrintAgain);
        AddButton(5, "Copia de seguridad ahora", Color.FromArgb(60, 60, 90), delegate { Backup(true); });
        AddButton(6, "Administracion (frase del evento)", Color.FromArgb(60, 60, 90), delegate { Process.Start("http://127.0.0.1:8000/#/setup"); });
        AddButton(7, "Cerrar espejo", Color.FromArgb(150, 50, 50), StopMirror);

        info.SetBounds(20, 570, 420, 70);
        info.Font = new Font("Segoe UI", 9f);
        info.ForeColor = Color.Silver;
        Controls.Add(info);

        timer.Interval = 5000;
        timer.Tick += delegate { RefreshState(); };
        timer.Start();
        RefreshState();
    }

    void AddButton(int row, string text, Color color, EventHandler click)
    {
        var b = new Button();
        b.Text = text;
        b.SetBounds(20, 56 + row * 63, 420, 54);
        b.FlatStyle = FlatStyle.Flat;
        b.FlatAppearance.BorderSize = 0;
        b.BackColor = color;
        b.ForeColor = Color.White;
        b.Click += click;
        Controls.Add(b);
    }

    static bool IsUp()
    {
        try
        {
            var r = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:8000/");
            r.Timeout = 1500;
            using (var resp = (HttpWebResponse)r.GetResponse()) return resp.StatusCode == HttpStatusCode.OK;
        }
        catch { return false; }
    }

    static int Count(string dir)
    {
        return Directory.Exists(dir) ? Directory.GetFiles(dir, "*.jpg").Count(f => !f.Contains("_hidden")) : 0;
    }

    void RefreshState()
    {
        bool up = IsUp();
        status.Text = up ? "Espejo funcionando" : "Espejo apagado";
        status.ForeColor = up ? Color.LightGreen : Color.Orange;
        tick++;
        if (tick % 12 == 1) Backup(false); // about once a minute, automatically
        info.Text = "Fotos hechas: " + Count(Photos) + "\nFotos guardadas en: " + Photos + "\nCopia automatica en: " + BackupRoot;
    }

    // starts a capture on the running booth (same thing as the F / T keys on the screen)
    void TakePhoto(string action)
    {
        try
        {
            var r = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:8000/api/actions/" + action);
            r.Timeout = 5000;
            using (r.GetResponse()) { }
        }
        catch (Exception ex) { MessageBox.Show("No se pudo sacar la foto. Esta iniciado el espejo? " + ex.Message); }
    }

    static void Open(string dir)
    {
        Directory.CreateDirectory(dir);
        Process.Start("explorer.exe", "\"" + dir + "\"");
    }

    void StartMirror(object s, EventArgs e)
    {
        var psi = new ProcessStartInfo("powershell.exe",
            "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + Path.Combine(Root, "kiosk", "start-kiosk.ps1") + "\"");
        psi.WorkingDirectory = Root;
        psi.CreateNoWindow = true;
        psi.UseShellExecute = false;
        Process.Start(psi);
        status.Text = "Iniciando (puede tardar un minuto)...";
    }

    void StopMirror(object s, EventArgs e)
    {
        if (MessageBox.Show("Cerrar el espejo? Las fotos ya hechas quedan guardadas.", "Cerrar", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
        Backup(false);
        // closes only the kiosk browser (own profile) and the photobooth server; nothing else
        var kill = new ProcessStartInfo("powershell.exe",
            "-NoProfile -Command \"Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'msedge.exe' -and $_.CommandLine -like '*photobooth-kiosk-profile*') -or ($_.Name -like 'python*' -and $_.CommandLine -like '*photobooth*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }\"");
        kill.CreateNoWindow = true;
        kill.UseShellExecute = false;
        Process.Start(kill);
    }

    void PrintAgain(object s, EventArgs e)
    {
        var dlg = new OpenFileDialog();
        dlg.InitialDirectory = Photos;
        dlg.Filter = "Fotos (*.jpg)|*.jpg";
        dlg.Multiselect = true;
        dlg.Title = "Elegi las fotos a imprimir (ordena por fecha para ver las ultimas)";
        if (dlg.ShowDialog() != DialogResult.OK) return;
        foreach (var f in dlg.FileNames)
        {
            var psi = new ProcessStartInfo(f);
            psi.Verb = "print"; // sends it to the default printer
            psi.UseShellExecute = true;
            try { Process.Start(psi); } catch (Exception ex) { MessageBox.Show("No se pudo imprimir " + Path.GetFileName(f) + ": " + ex.Message); }
        }
    }

    // copies photos and originals that are not backed up yet. Never deletes anything.
    void Backup(bool verbose)
    {
        int copied = 0;
        try
        {
            copied += CopyNew(Photos, Path.Combine(BackupRoot, "Fotos"), true);
            copied += CopyNew(Originals, Path.Combine(BackupRoot, "Originales"), false);
        }
        catch (Exception ex)
        {
            if (verbose) MessageBox.Show("No se pudo copiar: " + ex.Message);
            return;
        }
        if (verbose)
        {
            MessageBox.Show("Copia lista: " + copied + " archivos nuevos.\n" + BackupRoot);
            Open(BackupRoot);
        }
    }

    static int CopyNew(string from, string to, bool skipHidden)
    {
        if (!Directory.Exists(from)) return 0;
        Directory.CreateDirectory(to);
        int n = 0;
        foreach (var f in Directory.GetFiles(from))
        {
            if (skipHidden && f.Contains("_hidden")) continue;
            var dest = Path.Combine(to, Path.GetFileName(f));
            if (File.Exists(dest)) continue;
            try { File.Copy(f, dest); n++; } catch { }
        }
        return n;
    }

    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.Run(new Espejo());
    }
}
