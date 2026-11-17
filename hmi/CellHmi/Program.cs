// 물류 분류 셀 HMI (Modbus TCP 클라이언트)
// Coil 0 피킹 요청 · 1 셀 정상 · 2 요청 수락 · 3 동작 중 · 4 피킹 완료
// Coil 5 박스 도착(쓰기) · 6 알람 리셋(쓰기) · 7 알람
using System.Net.Sockets;
using NModbus;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new HmiForm());
    }
}

class HmiForm : Form
{
    const string Host = "127.0.0.1";
    const int Port = 5020;
    const byte UnitId = 1;
    const ushort BoxCoil = 5, ResetCoil = 6;

    // 화면에 표시할 신호: (Coil 번호, 이름, 켜졌을 때 색)
    readonly (ushort addr, string name, Color on)[] signals =
    {
        (0, "피킹 요청", Color.Gold),
        (1, "셀 정상",   Color.LimeGreen),
        (2, "요청 수락", Color.DeepSkyBlue),
        (3, "동작 중",   Color.Orange),
        (4, "피킹 완료", Color.LimeGreen),
        (7, "알람",      Color.Red),
    };

    readonly Label[] lamps;
    readonly Label status = new() { AutoSize = true, Location = new Point(20, 20), Font = new Font("맑은 고딕", 11) };
    readonly System.Windows.Forms.Timer poll = new() { Interval = 200 };   // 200ms마다 PLC 상태 읽기

    TcpClient tcp;
    IModbusMaster master;

    public HmiForm()
    {
        Text = "물류 분류 셀 HMI";
        ClientSize = new Size(560, 300);
        Font = new Font("맑은 고딕", 10);
        Controls.Add(status);

        lamps = new Label[signals.Length];
        for (int i = 0; i < signals.Length; i++)
        {
            lamps[i] = new Label
            {
                Text = signals[i].name,
                TextAlign = ContentAlignment.MiddleCenter,
                BorderStyle = BorderStyle.FixedSingle,
                BackColor = Color.Gainsboro,
                Size = new Size(80, 60),
                Location = new Point(20 + i * 88, 60),
            };
            Controls.Add(lamps[i]);
        }

        var connectBtn = MakeButton("연결", 20, (s, e) => Connect());
        var boxBtn     = MakeButton("박스 도착", 160, (s, e) => Write(BoxCoil));
        var resetBtn   = MakeButton("알람 리셋", 300, (s, e) => Write(ResetCoil));
        Controls.AddRange(new Control[] { connectBtn, boxBtn, resetBtn });

        poll.Tick += (s, e) => ReadSignals();
        ShowDisconnected("연결 안 됨");
    }

    Button MakeButton(string text, int x, EventHandler onClick)
    {
        var b = new Button { Text = text, Size = new Size(120, 50), Location = new Point(x, 170) };
        b.Click += onClick;
        return b;
    }

    void Connect()
    {
        try
        {
            tcp?.Close();
            tcp = new TcpClient(Host, Port);
            master = new ModbusFactory().CreateMaster(tcp);
            master.Transport.ReadTimeout = 1000;
            master.Transport.WriteTimeout = 1000;
            status.Text = $"연결됨 ({Host}:{Port})";
            status.ForeColor = Color.Green;
            poll.Start();
        }
        catch (Exception ex)
        {
            ShowDisconnected("연결 실패: " + ex.Message);
        }
    }

    void ReadSignals()
    {
        try
        {
            bool[] coils = master.ReadCoils(UnitId, 0, 8);
            for (int i = 0; i < signals.Length; i++)
                lamps[i].BackColor = coils[signals[i].addr] ? signals[i].on : Color.Gainsboro;
        }
        catch (Exception)
        {
            // 응답이 없으면 화면이 마지막 상태를 보여주지 않도록 모두 회색으로 바꾼다
            ShowDisconnected("통신 끊김: PLC 응답 없음");
        }
    }

    void Write(ushort coil)
    {
        if (master == null) return;
        try { master.WriteSingleCoil(UnitId, coil, true); }   // PLC가 읽은 뒤 스스로 끈다
        catch (Exception) { ShowDisconnected("통신 끊김: 쓰기 실패"); }
    }

    void ShowDisconnected(string msg)
    {
        poll.Stop();
        master = null;
        tcp?.Close();
        tcp = null;
        status.Text = msg;
        status.ForeColor = Color.Red;
        foreach (var lamp in lamps) lamp.BackColor = Color.Gainsboro;
    }
}
