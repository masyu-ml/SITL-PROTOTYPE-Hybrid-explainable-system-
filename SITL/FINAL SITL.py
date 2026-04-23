import sys
import pandas as pd
import numpy as np
import datetime
import smtplib
import threading
import socket
from email.message import EmailMessage
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtPrintSupport import QPrinter
import pyqtgraph as pg
from sklearn.tree import DecisionTreeClassifier

# ─────────────────────────────────────────────
#  DESIGN SYSTEM (AUTONOMOUS CONTROL NODE)
# ─────────────────────────────────────────────
DASHBOARD_STYLE = """
    QMainWindow { background-color: #0A0A0C; }
    QGroupBox {
        color: #8892B0; font-family: 'Segoe UI'; font-weight: bold; font-size: 12px;
        border: 1px solid #1E293B; margin-top: 12px; padding-top: 15px;
        background-color: #0F172A; border-radius: 8px;
    }
    QLabel { color: #CBD5E1; font-family: 'Segoe UI'; }

    #StatusHeader { font-size: 36px; font-weight: 900; letter-spacing: 2px; border-radius: 8px; padding: 15px; }
    #InstructionCard { font-size: 20px; font-weight: bold; color: #FFFFFF; background-color: #1E293B; border-radius: 8px; padding: 20px; }
    #VitalityBar { border: 2px solid #334155; border-radius: 10px; background-color: #0F172A; text-align: center; color: transparent; height: 30px; }
    #VitalityBar::chunk { background-color: #10B981; border-radius: 8px; }

    #DigitalReadout { color: #FFFFFF; font-family: 'Consolas'; font-size: 20px; font-weight: bold; }
    QLineEdit { background-color: #1E293B; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; font-family: 'Consolas'; font-size: 14px; padding: 6px; }

    QPushButton { background-color: #1E293B; border: 1px solid #334155; color: #F8FAFC; font-size: 12px; font-weight: bold; padding: 10px; border-radius: 4px; }
    QPushButton:hover { background-color: #334155; }
    QPushButton#PauseBtn { color: #38BDF8; border: 1px solid #38BDF8; }
    QPushButton#FaultBtn  { color: #EF4444; border: 1px solid #7F1D1D; background-color: #450A0A; }
    QPushButton#ExportBtn { color: #10B981; border: 1px solid #064E3B; background-color: #022C22; font-size: 14px; padding: 15px;}

    /* ESP32 Connect Button */
    QPushButton#ConnectBtn { background-color: #0C4A6E; color: #38BDF8; border: 1px solid #0284C7; font-size: 14px; padding: 12px;}
    QPushButton#ConnectBtn:hover { background-color: #0284C7; color: white;}

    QListWidget#NotificationFeed { background-color: #0F172A; color: #94A3B8; border: 1px solid #1E293B; border-radius: 8px; font-family: 'Consolas'; font-size: 13px; padding: 10px; }

    /* Warp Slider Styling */
    QSlider::groove:horizontal { border: 1px solid #334155; height: 6px; background: #0A0A0C; border-radius: 3px; }
    QSlider::handle:horizontal { background: #38BDF8; width: 14px; margin: -5px 0; border-radius: 7px; }
    QSlider:disabled { opacity: 0.5; }
"""

# ─────────────────────────────────────────────
#  FUZZY ENGINE
# ─────────────────────────────────────────────
CRITICAL_RULES = {'Rule 8', 'Rule 9', 'Rule 10', 'Rule 11', 'Rule 12', 'Rule 13', 'Rule 14', 'Rule 15'}
MARGINAL_RULES = {'Rule 3', 'Rule 4', 'Rule 5', 'Rule 6', 'Rule 7'}
NOMINAL_RULES = {'Rule 1', 'Rule 2'}


def fuzzy_check(i, v, t):
    c_s = 'High' if i > 568 else ('Low' if i < 445 else 'Normal')
    v_s = 'Stable' if -32 <= v <= -7 else ('CriticalLow' if v < -32 else 'HighSpike')
    t_s = 'Critical' if t > 20 else ('Marginal' if t >= 16 else 'Normal')
    triggered = set()
    if c_s == 'Normal' and v_s == 'Stable' and t_s == 'Normal':   triggered.add('Rule 1')
    if c_s == 'Low' and v_s == 'Stable' and t_s == 'Normal':   triggered.add('Rule 2')
    if c_s == 'Normal' and v_s == 'Stable' and t_s == 'Marginal': triggered.add('Rule 3')
    if c_s == 'Normal' and v_s == 'CriticalLow' and t_s == 'Normal':   triggered.add('Rule 4')
    if c_s == 'Normal' and v_s == 'HighSpike' and t_s == 'Normal':   triggered.add('Rule 5')
    if c_s == 'Low' and v_s == 'Stable' and t_s == 'Marginal': triggered.add('Rule 6')
    if c_s == 'High' and v_s == 'Stable' and t_s == 'Normal':   triggered.add('Rule 7')
    if t_s == 'Critical': triggered.add('Rule 8')
    if c_s == 'High' and t_s == 'Marginal': triggered.add('Rule 9')
    if c_s == 'High' and v_s == 'CriticalLow': triggered.add('Rule 10')
    if c_s == 'High' and v_s == 'HighSpike': triggered.add('Rule 11')
    if v_s == 'CriticalLow' and t_s == 'Marginal': triggered.add('Rule 12')
    if v_s == 'HighSpike' and t_s == 'Marginal': triggered.add('Rule 13')
    if c_s == 'Low' and v_s == 'CriticalLow' and t_s == 'Marginal': triggered.add('Rule 14')
    if c_s == 'Low' and v_s == 'HighSpike' and t_s != 'Normal': triggered.add('Rule 15')

    def sort_rules(rule_set):
        return sorted(rule_set, key=lambda x: int(x.split(' ')[1]))

    if triggered & CRITICAL_RULES: return 'CRITICAL', sort_rules(triggered & CRITICAL_RULES)
    if triggered & MARGINAL_RULES: return 'MARGINAL', sort_rules(triggered & MARGINAL_RULES)
    if triggered & NOMINAL_RULES:  return 'NOMINAL', sort_rules(triggered & NOMINAL_RULES)
    return 'NOMINAL', []


# ─────────────────────────────────────────────
#  REFERENCE POP-UP WINDOW (XAI)
# ─────────────────────────────────────────────
class SystemLogicWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SYSTEM LOGIC & THRESHOLDS REFERENCE")
        self.resize(900, 800)
        self.setStyleSheet("background-color: #0A0A0C; color: #CBD5E1; font-family: 'Segoe UI';")

        layout = QVBoxLayout(self)
        header = QLabel("⚙️ HYBRID XAI ARBITRATION LOGIC")
        header.setStyleSheet(
            "background-color: #1E293B; color: #38BDF8; font-size: 20px; font-weight: bold; padding: 15px; border-radius: 8px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        doc_text = QTextEdit()
        doc_text.setReadOnly(True)
        doc_text.setStyleSheet(
            "QTextEdit { background-color: #0F172A; color: #CBD5E1; font-family: 'Consolas'; font-size: 13px; border: 1px solid #334155; border-radius: 8px; padding: 20px; } "
            "h2 { color: #38BDF8; font-family: 'Segoe UI'; font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 5px; margin-top: 20px;} "
            "h3.nominal { color: #10B981; } "
            "h3.marginal { color: #F59E0B; } "
            "h3.critical { color: #EF4444; } "
            "ul { margin-top: 5px; margin-bottom: 15px; }"
        )

        doc_text.setHtml("""
        <h2>LAYER 1: MEMBERSHIP BOUNDARIES</h2>
        <ul>
            <li><b>Current (I):</b> Low (&lt; 445A) | Normal (445–568A) | High (&gt; 568A)</li>
            <li><b>Voltage (V):</b> Sag (&lt; -32V) | Stable (-32V to -7V) | Spike (&gt; -7V)</li>
            <li><b>Temperature (T):</b> Normal (&lt; 16°C) | Marginal (16–20°C) | Critical (&gt; 20°C)</li>
        </ul>

        <h2>LAYER 1: DETERMINISTIC FUZZY RULES (N=15)</h2>

        <h3 class='nominal'>🟢 NOMINAL STATE RULES (Proceed Normally)</h3>
        <ul>
            <li><b>Rule 1:</b> IF (I is Normal) AND (V is Stable) AND (T is Normal)</li>
            <li><b>Rule 2:</b> IF (I is Low) AND (V is Stable) AND (T is Normal)</li>
        </ul>

        <h3 class='marginal'>🟡 MARGINAL STATE RULES (Caution / Warning)</h3>
        <ul>
            <li><b>Rule 3:</b> IF (I is Normal) AND (V is Stable) AND (T is Marginal) -> <i>Early thermal warning</i></li>
            <li><b>Rule 4:</b> IF (I is Normal) AND (V is Sag) AND (T is Normal) -> <i>Undervoltage transient</i></li>
            <li><b>Rule 5:</b> IF (I is Normal) AND (V is Spike) AND (T is Normal) -> <i>Overvoltage transient</i></li>
            <li><b>Rule 6:</b> IF (I is Low) AND (V is Stable) AND (T is Marginal) -> <i>Cooling degradation</i></li>
            <li><b>Rule 7:</b> IF (I is High) AND (V is Stable) AND (T is Normal) -> <i>High load prior to thermal rise</i></li>
        </ul>

        <h3 class='critical'>🔴 CRITICAL STATE RULES (Emergency Stop)</h3>
        <ul>
            <li><b>Rule 8:</b> IF (T is Critical) -> <i>Absolute thermal override</i></li>
            <li><b>Rule 9:</b> IF (I is High) AND (T is Marginal) -> <i>Severe overload heating</i></li>
            <li><b>Rule 10:</b> IF (I is High) AND (V is Sag) -> <i>Short circuit signature</i></li>
            <li><b>Rule 11:</b> IF (I is High) AND (V is Spike) -> <i>Severe electrical fault</i></li>
            <li><b>Rule 12:</b> IF (V is Sag) AND (T is Marginal) -> <i>Undervoltage + abnormal heating</i></li>
            <li><b>Rule 13:</b> IF (V is Spike) AND (T is Marginal) -> <i>Overvoltage + abnormal heating</i></li>
            <li><b>Rule 14:</b> IF (I is Low) AND (V is Sag) AND (T is Marginal) -> <i>Phase loss / supply failure</i></li>
            <li><b>Rule 15:</b> IF (I is Low) AND (V is Spike) AND (T is not Normal) -> <i>Regulation failure</i></li>
        </ul>

        <h2>LAYER 2 & 3: Decision Tree and Explainable AI</h2>
        <ul>
            <li><b>Layer 2 (Decision Tree):</b> Analyzes a 10-sample sliding window. Extracts features: <code>Temp_Diff_Max_mean</code>, <code>Ia_std</code>, and <code>Current_RMS_slope</code> to predict anomalies before Fuzzy thresholds are breached.</li>
            <li><b>Layer 3 (Physics Shield):</b> 
                <br>• If <b>Z &gt; 1.0 Ω</b>: Hard Open Circuit Override.
                <br>• If AI predicts Short Circuit but <b>Z &gt; 0.036 Ω</b>: False Positive Rejection.
            </li>
        </ul>
        """)
        layout.addWidget(doc_text)

        close_btn = QPushButton("CLOSE REFERENCE GUIDE")
        close_btn.setStyleSheet(
            "background-color: #1E293B; border: 1px solid #334155; color: white; padding: 12px; font-weight: bold; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ─────────────────────────────────────────────
#  DRAG & DROP TELEMETRY ZONE
# ─────────────────────────────────────────────
class FileDropZone(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.locked = False
        self.reset_visuals()
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)

    def reset_visuals(self):
        self.locked = False
        self.setText("📁 CONNECT SENSOR TELEMETRY (DATASET)\nDrag & Drop .CSV or Wait for Wi-Fi Link")
        self.setStyleSheet(
            "QLabel { background-color: #0F172A; color: #38BDF8; font-weight: bold; font-size: 14px; border: 2px dashed #334155; border-radius: 8px; padding: 25px; } QLabel:hover { background-color: #1E293B; border: 2px dashed #38BDF8; }")

    def lock_visuals(self):
        self.locked = True
        # Remove any mention of BACHA or Auto-Mapping
        self.setText("🔒 SENSOR NODE LINKED\nReceiving Hardware Telemetry")
        self.setStyleSheet(
            "QLabel { background-color: #0A0A0C; color: #10B981; font-weight: bold; font-size: 14px; border: 2px solid #065F46; border-radius: 8px; padding: 25px; }")
    def dragEnterEvent(self, event):
        if not self.locked and event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        if self.locked: return
        urls = event.mimeData().urls()
        if urls:
            fp = urls[0].toLocalFile()
            if fp.endswith('.csv'): self.file_dropped.emit(fp)

    def mousePressEvent(self, event):
        if self.locked: return
        if event.button() == Qt.LeftButton:
            fp, _ = QFileDialog.getOpenFileName(self, "Select Telemetry CSV", "", "CSV Files (*.csv)")
            if fp: self.file_dropped.emit(fp)


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class NASAMissionControl(QMainWindow):
    WINDOW_SIZE = 10
    L2_FEATURES = ['Temp_Diff_Max_mean', 'Ia_std', 'Power_DC_mean', 'VDC_mean', 'Current_RMS_slope', 'Temp_Max_slope',
                   'T2_mean', 'T3_mean']

    ui_update_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AUTONOMOUS CONTROL NODE")
        self.resize(1400, 950)
        self.setStyleSheet(DASHBOARD_STYLE)

        # 👉 HARDWARE-IN-THE-LOOP (ESP32) SETTINGS
        self.ESP32_IP = "192.168.1.16"  # CHANGE THIS TO MATCH YOUR ESP32 IP
        self.UDP_PORT = 8080
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind(("", self.UDP_PORT))
        self.esp_connected = False

        self.df = pd.DataFrame()
        self.data_index = 0
        self.paused = True
        self.manual_mode = False
        self.continuous_mode = False
        self.buffer_size = 150
        self.live_window = []
        self.plots = {}
        self.buffers = {'VDC': [], 'AMPS': [], 'TEMP': [], 'DELTA': []}

        self.hidden_console = QTextEdit()
        self.hidden_console.setVisible(False)

        self.ui_update_signal.connect(self.push_notification)

        self.init_ui()
        self.load_reference_data()
        self.train_layer2()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(50)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)

        # 👉 OS Notifications Init
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray_icon.show()

        # LEFT PANEL: DRIVER DISPLAY
        left_panel = QWidget()
        left_lay = QVBoxLayout(left_panel)

        self.status_header = QLabel("AWAITING TELEMETRY")
        self.status_header.setObjectName("StatusHeader")
        self.status_header.setAlignment(Qt.AlignCenter)
        self.status_header.setStyleSheet("background-color: #334155; color: #FFFFFF;")
        left_lay.addWidget(self.status_header)

        vitality_box = QGroupBox("SYSTEM VITALITY")
        v_lay = QVBoxLayout(vitality_box)
        self.health_bar = QProgressBar()
        self.health_bar.setObjectName("VitalityBar")
        self.health_bar.setValue(0)
        v_lay.addWidget(self.health_bar)
        left_lay.addWidget(vitality_box)

        instruction_box = QGroupBox("SYSTEM DIRECTIVES")
        i_lay = QVBoxLayout(instruction_box)
        self.instruction_label = QLabel("Standby mode. Please connect sensor telemetry to begin.")
        self.instruction_label.setObjectName("InstructionCard")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("color: #8892B0;")
        i_lay.addWidget(self.instruction_label)
        left_lay.addWidget(instruction_box)

        tel_box = QGroupBox("BACKGROUND SENSORS")
        self.tel_grid = QGridLayout(tel_box)
        self.create_tile("VOLTAGE", "VDC", 0, 0)
        self.create_tile("CURRENT", "AMPS", 0, 1)
        self.create_tile("TEMP", "TEMP", 1, 0)
        self.create_tile("DELTA", "DELTA", 1, 1)
        left_lay.addWidget(tel_box)

        # 👉 Notification Feed
        notif_box = QGroupBox("LIVE SYSTEM NOTIFICATIONS")
        n_lay = QVBoxLayout(notif_box)
        self.notif_feed = QListWidget()
        self.notif_feed.setObjectName("NotificationFeed")
        n_lay.addWidget(self.notif_feed)
        left_lay.addWidget(notif_box)

        # RIGHT PANEL: CONTROL CENTER
        right_panel = QWidget()
        right_panel.setFixedWidth(350)
        right_lay = QVBoxLayout(right_panel)

        data_box = QGroupBox("MISSION DATA LOAD")
        data_lay = QVBoxLayout(data_box)

        # 👉 ESP32 HIL LINK BUTTON
        self.connect_btn = QPushButton("📡 ESTABLISH SENSOR NODE LINK")
        self.connect_btn.setObjectName("ConnectBtn")
        self.connect_btn.clicked.connect(self.toggle_esp_link)
        data_lay.addWidget(self.connect_btn)

        self.drop_zone = FileDropZone()
        self.drop_zone.file_dropped.connect(self.load_custom_telemetry)
        data_lay.addWidget(self.drop_zone)
        right_lay.addWidget(data_box)

        # 👉 OPERATOR CONFIGURATION (Email Config)
        op_box = QGroupBox("OPERATOR CONFIGURATION")
        op_lay = QVBoxLayout(op_box)
        self.email_input = QLineEdit("")
        self.email_input.setPlaceholderText("Enter receiver email...")
        op_lay.addWidget(QLabel("Alert Notification Email:"))
        op_lay.addWidget(self.email_input)
        right_lay.addWidget(op_box)

        ctrl_box = QGroupBox("AUTONOMOUS CONTROL")
        ctrl_lay = QVBoxLayout(ctrl_box)
        self.pause_btn = QPushButton("PAUSE MISSION")
        self.pause_btn.setObjectName("PauseBtn")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.reset_btn = QPushButton("RESET VEHICLE")
        self.reset_btn.clicked.connect(self.reset_mission)

        # 👉 THE WARP SLIDER
        warp_lay = QHBoxLayout()
        warp_lbl = QLabel("Warp:")
        warp_lbl.setStyleSheet("color: #38BDF8; font-weight: bold;")
        self.warp_slider = QSlider(Qt.Horizontal)
        self.warp_slider.setRange(10, 200)
        self.warp_slider.setValue(50)
        self.warp_slider.setInvertedAppearance(True)
        self.warp_slider.valueChanged.connect(lambda v: self.timer.setInterval(v))
        warp_lay.addWidget(warp_lbl)
        warp_lay.addWidget(self.warp_slider)

        # 👉 CONTINUOUS MODE / OVERRIDE TOGGLE
        self.loop_toggle = QCheckBox("Enable Continuous Mode (Bypass E-Stops)")
        self.loop_toggle.setStyleSheet("color: #10B981; font-weight: bold; margin-top: 5px;")
        self.loop_toggle.toggled.connect(self.toggle_continuous_mode)

        ctrl_lay.addWidget(self.pause_btn)
        ctrl_lay.addWidget(self.reset_btn)
        ctrl_lay.addLayout(warp_lay)
        ctrl_lay.addWidget(self.loop_toggle)
        right_lay.addWidget(ctrl_box)

        stress_box = QGroupBox("MANUAL TEST CONTROLS")
        stress_lay = QVBoxLayout(stress_box)
        self.manual_toggle = QCheckBox("Enable Manual Override")
        self.manual_toggle.toggled.connect(self.toggle_manual_mode)
        self.i_input = self.create_input("Current (A)", "510.0")
        self.v_input = self.create_input("Voltage (V)", "-12.0")
        self.t_input = self.create_input("Temp (°C)", "14.5")
        stress_lay.addWidget(self.manual_toggle)
        stress_lay.addLayout(self.i_input[0]);
        stress_lay.addLayout(self.v_input[0]);
        stress_lay.addLayout(self.t_input[0])
        right_lay.addWidget(stress_box)

        fault_box = QGroupBox("INJECT FAULT")
        f_lay = QVBoxLayout(fault_box)
        for f in ["short_circuit", "open_circuit", "overheating"]:
            btn = QPushButton(f"Simulate {f.replace('_', ' ').title()}")
            btn.setObjectName("FaultBtn")
            btn.clicked.connect(lambda checked, ft=f: self.inject_fault(ft))
            f_lay.addWidget(btn)
        right_lay.addWidget(fault_box)

        right_lay.addStretch()

        self.rules_btn = QPushButton("🔍 VIEW SYSTEM LOGIC & THRESHOLDS")
        self.rules_btn.setStyleSheet(
            "color: #38BDF8; border: 1px solid #0369A1; background-color: #0C4A6E; font-size: 13px; padding: 12px; margin-bottom: 10px;")
        self.rules_btn.clicked.connect(self.show_logic_window)
        right_lay.addWidget(self.rules_btn)

        self.exp_btn = QPushButton("DOWNLOAD FORENSIC REPORT (.PDF)")
        self.exp_btn.setObjectName("ExportBtn")
        self.exp_btn.clicked.connect(self.export_report)
        right_lay.addWidget(self.exp_btn)

        main_lay.addWidget(left_panel);
        main_lay.addWidget(right_panel)

    def create_tile(self, title, key, r, c):
        box = QWidget();
        v = QVBoxLayout(box)
        h = QHBoxLayout();
        h.addWidget(QLabel(title));
        val = QLabel("0.00");
        val.setObjectName("DigitalReadout")
        h.addStretch();
        h.addWidget(val);
        v.addLayout(h)
        p = pg.PlotWidget();
        p.setBackground('#0F172A');
        p.setFixedHeight(60)
        curve = p.plot(pen=pg.mkPen('#38BDF8', width=2))
        v.addWidget(p);
        self.tel_grid.addWidget(box, r, c);
        self.plots[key] = (val, curve)

    def create_input(self, label, default):
        lay = QHBoxLayout();
        edit = QLineEdit(default)
        edit.setValidator(QDoubleValidator(-1000.0, 1000.0, 2))
        lay.addWidget(QLabel(label));
        lay.addWidget(edit)
        return lay, edit

    # 👉 THE NEW SMART AUTO-LOADER ESP32 CONNECTION
    def toggle_esp_link(self):
        if not self.esp_connected:
            # Silent Load (This stays the same for a smooth connection)
            if self.df.empty:
                try:
                    self.df = pd.read_csv("BACHA_PRESENT_STATE.csv")
                except:
                    pass

            self.esp_connected = True
            self.connect_btn.setText("🔌 DISCONNECT SENSOR NODE")
            self.connect_btn.setStyleSheet("background-color: #047857; color: white;")
            self.drop_zone.lock_visuals()
            self.manual_toggle.setEnabled(False)
            self.warp_slider.setEnabled(False)
            self.push_notification("HIL Link Established.", "SUCCESS")
        else:
            # --- THE DISCONNECT FIX ---
            self.esp_connected = False
            self.paused = True
            self.pause_btn.setText("RESUME MISSION")

            # 1. 🔥 FIX: WIPE DATA MEMORY
            self.df = pd.DataFrame()  # Clear the CSV from memory
            self.data_index = 0  # Reset the pointer

            # 2. 🔥 FIX: RESET THE UI HEADERS
            self.status_header.setText("AWAITING TELEMETRY")
            self.status_header.setStyleSheet("background-color: #334155; color: white")
            self.instruction_label.setText("Hardware unlinked. Please reconnect sensor node or load CSV.")
            self.health_bar.setValue(0)

            # 3. 🔥 FIX: CLEAR THE GRAPHS (Optional but looks professional)
            for k in self.buffers: self.buffers[k] = []
            for k in self.plots:
                self.plots[k][1].setData([])
                self.plots[k][0].setText("0.00")

            # Reset Visuals
            self.connect_btn.setText("📡 ESTABLISH SENSOR NODE LINK")
            self.connect_btn.setStyleSheet("")
            self.drop_zone.reset_visuals()
            self.manual_toggle.setEnabled(True)
            self.warp_slider.setEnabled(True)

            self.push_notification("HIL Link Terminated. Memory Purged.", "INFO")

    # 👉 Notification System
    def push_notification(self, msg, level="INFO"):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        icon_emoji, tray_type = "ℹ️", QSystemTrayIcon.Information
        if level == "WARN":
            icon_emoji, tray_type = "⚠️", QSystemTrayIcon.Warning
        elif level == "CRIT":
            icon_emoji, tray_type = "🛑", QSystemTrayIcon.Critical
        elif level == "SUCCESS":
            icon_emoji, tray_type = "✅", QSystemTrayIcon.Information

        self.notif_feed.addItem(f"[{ts}] {icon_emoji} {msg}")
        self.notif_feed.scrollToBottom()
        self.tray_icon.showMessage(f"Autonomous Node: {level}", msg, tray_type, 3000)

    # 👉 Background Email Sender
    def send_emergency_email(self, fault_name):
        SENDER_EMAIL = "avtelemetry@gmail.com"
        APP_PASSWORD = "auqq ugsh viwy rsdc"

        RECEIVER_EMAIL = self.email_input.text().strip()

        if not RECEIVER_EMAIL:
            self.ui_update_signal.emit("Email Failed: Operator email not configured.", "WARN")
            return

        def send():
            try:
                msg = EmailMessage()
                msg.set_content(
                    f"CRITICAL ALERT: The Autonomous Control Node has recorded a critical event: {fault_name}.\n\nPlease check the telemetry dashboard immediately.")
                msg['Subject'] = f"🚨 AV FLEET ALERT: {fault_name}"
                msg['From'] = SENDER_EMAIL
                msg['To'] = RECEIVER_EMAIL

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
                server.quit()
                self.ui_update_signal.emit(f"Emergency Email dispatched to {RECEIVER_EMAIL}.", "SUCCESS")
            except Exception as e:
                self.ui_update_signal.emit(f"Email Failed (Check Password/Auth): {e}", "WARN")

        threading.Thread(target=send, daemon=True).start()

    def show_logic_window(self):
        self.logic_win = SystemLogicWindow()
        self.logic_win.exec_()

    def toggle_pause(self):
        if self.df.empty and not self.manual_mode and not self.esp_connected: return
        self.paused = not self.paused
        self.pause_btn.setText("RESUME MISSION" if self.paused else "PAUSE MISSION")

        if self.esp_connected:
            try:
                self.sock.sendto(b"PAUSE" if self.paused else b"RESUME", (self.ESP32_IP, self.UDP_PORT))
            except:
                pass

    def toggle_manual_mode(self, checked):
        self.manual_mode = checked
        # 🔥 CRITICAL: Clear the sliding window so the AI doesn't
        # think the jump from 0 to 500 is a "spike" or "fault"
        self.live_window.clear()

        if checked:
            self.paused = False
            self.pause_btn.setText("PAUSE MISSION")
            self.update_user_dashboard("NOMINAL")
            self.push_notification("Diagnostic Override Active. Reading static inputs.", "INFO")
        else:
            self.paused = True
            self.pause_btn.setText("RESUME MISSION")
            self.push_notification("Manual Override Deactivated.", "INFO")

    def toggle_continuous_mode(self, checked):
        self.continuous_mode = checked
        state = "Enabled (Bypassing E-Stops)" if checked else "Disabled"
        self.push_notification(f"Continuous Mode {state}", "INFO")

        if checked and self.paused and "CRITICAL" in getattr(self, 'last_ui_state', ''):
            self.paused = False
            self.pause_btn.setText("PAUSE MISSION")
            self.push_notification("E-Stop Override Activated. Resuming simulation.", "WARN")
            self.status_header.setText("CRITICAL FAULT (BYPASSED)")
            self.status_header.setStyleSheet("background-color: #7F1D1D; color: #FCA5A5")

    def load_custom_telemetry(self, fp):
        if self.esp_connected:
            self.push_notification("ERROR: Cannot load local CSV while Sensor Node link is active.", "CRIT")
            return

        try:
            self.df = pd.read_csv(fp)
            self.data_index = 0;
            self.paused = False;
            self.live_window.clear()
            for k in self.buffers: self.buffers[k] = []
            self.drop_zone.setText(f"✅ CONNECTED:\n{fp.split('/')[-1]}")
            self.push_notification("Telemetry Dataset Connected. Live analysis started.", "SUCCESS")
            self.update_user_dashboard("NOMINAL")
        except:
            self.drop_zone.setText("❌ ERROR READING FILE")

    def load_reference_data(self):
        try:
            self.win = pd.read_csv("BACHA_WINDOWED.csv")
        except:
            self.win = pd.DataFrame()

    def train_layer2(self):
        if self.win.empty: self.model = None; return
        available = list(self.win.columns)
        for f in self.L2_FEATURES:
            if f not in available: self.win[f] = 0.0
        self.model = DecisionTreeClassifier(max_depth=5, random_state=42)
        self.model.fit(self.win[self.L2_FEATURES], self.win['fault_type'])

    def update_simulation(self):
        if self.paused: return

        row = None

        # Priority 1: Manual Override
        if self.manual_toggle.isChecked():
            try:
                # 👉 FIX: Use self.i_input[1] because create_input returns (Layout, QLineEdit)
                i = float(self.i_input[1].text())
                v = float(self.v_input[1].text())
                t = float(self.t_input[1].text())
            except Exception as e:
                # If you leave a box empty, it defaults to Nominal values instead of zeros
                i, v, t = 510.0, -12.0, 14.5

                # Create a full row so the AI has all the columns it needs
            row = pd.Series({
                'Current_RMS': i, 'VDC': v, 'Temp_Max': t,
                'Temp_Diff_Max': 0.0, 'Ia': i, 'Power_DC': abs(v * i),
                'T2': t, 'T3': t
            })
            self.live_window = [row.to_dict()] * self.WINDOW_SIZE
            self.execute_arbitration(row)
            return  # Exit



        # Priority 2: ESP32 Hardware Link
        elif self.esp_connected:
            while True:
                try:
                    data, addr = self.sock.recvfrom(2048)
                    line = data.decode('utf-8').strip()

                    if "Time" in line or len(line) < 5:
                        continue

                    parts = line.split(',')
                    if not self.df.empty and len(parts) >= len(self.df.columns):
                        row_dict = {}
                        for idx, col in enumerate(self.df.columns):
                            try:
                                row_dict[col] = float(parts[idx])
                            except:
                                row_dict[col] = 0.0
                        row = pd.Series(row_dict)
                        self.execute_arbitration(row)
                except BlockingIOError:
                    break
                except Exception:
                    break
            return  # Exit here so we never hit the CSV logic below

            # Priority 3: Local CSV Playback
        elif not self.df.empty:
            if self.data_index >= len(self.df):
                self.data_index = 0
            row = self.df.iloc[self.data_index]
            self.data_index += 1
            self.execute_arbitration(row)
        else:
            if self.df.empty: return
            if self.data_index >= len(self.df):
                if self.continuous_mode:
                    self.data_index = 0
                    self.live_window.clear()
                else:
                    return
            row = self.df.iloc[self.data_index]
            self.data_index += 1

            self.execute_arbitration(row)

    def execute_arbitration(self, row):
        if row is None: return

        i = row['Current_RMS']
        v = row['VDC']
        t = row['Temp_Max']
        d = row.get('Temp_Diff_Max', 0.0)

        self.upd_plot("VDC", v)
        self.upd_plot("AMPS", i)
        self.upd_plot("TEMP", t)
        self.upd_plot("DELTA", d)

        # 👉 THE FIX: If manual mode is on, skip the AI transient check
        if self.manual_toggle.isChecked():
            l2_pred, l2_conf = None, 0.0
        else:
            l2_pred, l2_conf = self.compute_l2(row, abs(v/i) if i != 0 else 0)

        risk, rules = fuzzy_check(i, v, t)
        z = abs(v / i) if i > 5.0 else 0.0

        # Now the logic only triggers if it's a REAL threshold breach
        if risk == 'CRITICAL' or (l2_pred and l2_pred != 'normal' and l2_conf >= 0.70):
            self.arbitrate(row, rules, i, v, t, z, l2_pred, l2_conf)
        elif z > 1.0 and i > 5.0: # Hard Physics check for Open Circuit
            self.update_user_dashboard("CRITICAL")
        else:
            self.update_user_dashboard(risk)

    def compute_l2(self, row, z):
        if not self.model: return None, 0.0
        self.live_window.append(
            {'Current_RMS': row['Current_RMS'], 'Ia': row.get('Ia', row['Current_RMS']), 'Temp_Max': row['Temp_Max'],
             'Temp_Diff_Max': row.get('Temp_Diff_Max', 0), 'VDC': row['VDC'],
             'Power_DC': row.get('Power_DC', abs(row['VDC'] * row['Current_RMS'])),
             'T2': row.get('T2', row['Temp_Max']), 'T3': row.get('T3', row['Temp_Max'])})
        if len(self.live_window) > self.WINDOW_SIZE: self.live_window.pop(0)
        if len(self.live_window) < self.WINDOW_SIZE: return None, 0.0
        w = pd.DataFrame(self.live_window);
        x = np.arange(self.WINDOW_SIZE)
        feat = pd.DataFrame([[w['Temp_Diff_Max'].mean(), w['Ia'].std(), w['Power_DC'].mean(), w['VDC'].mean(),
                              np.polyfit(x, w['Current_RMS'], 1)[0], np.polyfit(x, w['Temp_Max'], 1)[0], w['T2'].mean(),
                              w['T3'].mean()]], columns=self.L2_FEATURES)
        return self.model.predict(feat)[0], float(self.model.predict_proba(feat)[0].max())

    def arbitrate(self, row, rules, i, v, t, z, l2_pred, l2_conf):
        verdict = "NOMINAL"

        # 1. PHYSICS LAYER (Highest Priority)
        if z > 1.0 and i > 5.0:
            verdict = "CRITICAL – OPEN_CIRCUIT"

        # 2. AI LAYER (Middle Priority - Specific labels from the ML Model)
        elif l2_pred and l2_pred != 'normal':
            verdict = f"CRITICAL – {l2_pred.upper()}"

        # 3. FUZZY LAYER (The "Safety Net" - Now with Smart Decoding)
        elif rules and any(r in CRITICAL_RULES for r in rules):
            # Let's decode the specific Rule into a descriptive fault
            if 'Rule 10' in rules or 'Rule 11' in rules:
                verdict = "CRITICAL – SHORT_CIRCUIT"
            elif 'Rule 8' in rules or 'Rule 9' in rules:
                verdict = "CRITICAL – THERMAL_RUNAWAY"
            elif 'Rule 14' in rules or 'Rule 15' in rules:
                verdict = "CRITICAL – REGULATION_FAILURE"
            else:
                verdict = "CRITICAL – HARDWARE_LIMIT"

        # Emergency Stop Logic
        if "CRITICAL" in verdict:
            if not self.continuous_mode:
                self.paused = True
        if "CRITICAL" in verdict or "MARGINAL" in verdict:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            log_entry = (
                f"<br><b>[FAULT DETECTED: {timestamp}]</b><br>"
                f"RESULT: <span style='color:red'>{verdict}</span><br>"
                f"DATA: {i:.1f}A | {v:.1f}V | {t:.1f}°C | Z: {z:.2f}Ω<br>"
                f"REASON: Rules {rules} | AI Conf: {l2_conf * 100:.1f}%<br>"
            )
            self.hidden_console.append(log_entry)
        self.update_user_dashboard(verdict)
        self.hidden_console.append(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Verdict: {verdict} | Rules: {rules}")

    def update_user_dashboard(self, v):
        if not hasattr(self, 'last_ui_state'): self.last_ui_state = ""

        if self.last_ui_state == v: return
        self.last_ui_state = v

        if "NOMINAL" in v:
            self.status_header.setText("ALL SYSTEMS GO");
            self.status_header.setStyleSheet("background-color: #10B981; color: white")
            self.instruction_label.setText("Autonomous mode engaged. No action required.");
            self.instruction_label.setStyleSheet("color: white")
            self.health_bar.setValue(100);
            self.health_bar.setStyleSheet("#VitalityBar::chunk { background-color: #10B981; }")
            self.push_notification("System stabilized. Resuming normal parameters.", "SUCCESS")

        elif "MARGINAL" in v:
            self.status_header.setText("CAUTION: SYSTEM STRESS");
            self.status_header.setStyleSheet("background-color: #F59E0B; color: white")
            self.instruction_label.setText("Reduce power. Motor stress detected.");
            self.instruction_label.setStyleSheet("color: #F59E0B")
            self.health_bar.setValue(60);
            self.health_bar.setStyleSheet("#VitalityBar::chunk { background-color: #F59E0B; }")
            self.push_notification("Thermal or electrical stress detected in Inverter.", "WARN")

        elif "CRITICAL" in v:
            fault_name = v.split('–')[-1].strip() if '–' in v else 'System Failure'

            if self.continuous_mode:
                self.status_header.setText("CRITICAL FAULT (BYPASSED)")
                self.status_header.setStyleSheet("background-color: #7F1D1D; color: #FCA5A5")
                self.instruction_label.setText(f"⚠️ E-STOP OVERRIDDEN.\nLogging Fault: {fault_name}")
                self.push_notification(f"CRITICAL FAULT: {fault_name}. System Overriding E-Stop.", "CRIT")
            else:
                self.status_header.setText("EMERGENCY SHUTDOWN")
                self.status_header.setStyleSheet("background-color: #EF4444; color: white")
                self.instruction_label.setText(f"🛑 AUTONOMOUS PULL-OVER INITIATED.\nFault: {fault_name}")
                self.push_notification(f"CRITICAL FAULT: {fault_name}. E-Stop Triggered.", "CRIT")

            self.instruction_label.setStyleSheet("color: #EF4444")
            self.health_bar.setValue(10);
            self.health_bar.setStyleSheet("#VitalityBar::chunk { background-color: #EF4444; }")

            self.send_emergency_email(fault_name)

    def upd_plot(self, k, v):
        lbl, curve = self.plots[k];
        lbl.setText(f"{v:.2f}");
        self.buffers[k].append(v);
        curve.setData(self.buffers[k][-self.buffer_size:])

    def inject_fault(self, ft):
        if self.esp_connected:
            cmd_map = {
                "short_circuit": b"INJECT_SHORT",
                "open_circuit": b"INJECT_OPEN",
                "overheating": b"INJECT_HEAT"
            }
            if ft in cmd_map:
                try:
                    self.sock.sendto(cmd_map[ft], (self.ESP32_IP, self.UDP_PORT))
                except:
                    pass

        if self.df.empty: return
        idx = self.df.index[self.df['fault_type'] == ft].tolist()
        if idx:
            self.data_index = idx[0];
            self.paused = False;
            self.manual_mode = False;
            self.live_window.clear()
            self.push_notification(f"Operator injected testing fault: {ft.upper()}", "WARN")

    def reset_mission(self):
        self.data_index = 0;
        self.paused = True;
        self.live_window.clear()

        if self.esp_connected:
            try:
                self.sock.sendto(b"RESET", (self.ESP32_IP, self.UDP_PORT))
            except:
                pass

        for k in self.buffers: self.buffers[k] = []
        for k in self.plots: self.plots[k][1].setData([]); self.plots[k][0].setText("0.00")

        if not self.df.empty or self.esp_connected:
            self.last_ui_state = ""
            self.update_user_dashboard("NOMINAL")
            self.status_header.setText("VEHICLE RESET (PAUSED)")
            self.status_header.setStyleSheet("background-color: #334155; color: white")
            self.instruction_label.setText("Telemetry rewound to start. Press 'RESUME MISSION' to play.")
            self.instruction_label.setStyleSheet("color: #8892B0")
            self.pause_btn.setText("RESUME MISSION")
            self.push_notification("Vehicle Rewound. Data retained.", "INFO")
        else:
            self.status_header.setText("AWAITING TELEMETRY");
            self.status_header.setStyleSheet("background-color: #334155; color: white")
            self.instruction_label.setText("Standby mode. Please connect sensor telemetry to begin.")
            self.health_bar.setValue(0)
            self.drop_zone.setText("📡 CONNECT SENSOR TELEMETRY (DATASET)\nDrag & Drop .CSV or Click to Browse")

        self.hidden_console.append(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] --- VEHICLE RESET ---")

    def export_report(self):
        # Create a professional header for the document
        header = f"""
        <h1 style='text-align: center; color: #1E293B;'>POWER SUBSYSTEM CONTROL NODE: FORENSIC DATA REPORT</h1>
        <p style='text-align: center;'><b>Mission Date:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p style='text-align: center;'><b>System Status:</b>Simulation</p>
        <hr style='border: 2px solid #334155;'>
        """

        # Save dialog
        fp, _ = QFileDialog.getSaveFileName(self, "Export Forensic Log", "XAI_Forensic_Report.pdf", "PDF (*.pdf)")
        if not fp: return

        # Setup Printer
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(fp)

        # Temporarily combine header + log
        full_document = QTextDocument()
        full_document.setHtml(header + self.hidden_console.toHtml())

        full_document.print_(printer)
        self.push_notification(f"Forensic Report Saved.", "SUCCESS")


if __name__ == "__main__":
    app = QApplication(sys.argv);
    w = NASAMissionControl();
    w.show();
    sys.exit(app.exec_())