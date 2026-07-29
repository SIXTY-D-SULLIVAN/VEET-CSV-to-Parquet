"""VEET Sensor_Data.csv / log.csv -> Parquet converter.

Standalone GUI utility. Converts the two raw files a VEET device writes
(Sensor_Data.csv, log.csv) into Parquet, without altering the originals.

Both files are heterogeneous logs: every line is
`epoch_timestamp, TAG, field..., field...` with a different field count per
TAG. There is no fixed schema, so rows are transcribed generically (padded
to the widest row in the file) rather than re-derived per sensor type - that
richer parsing already exists in VEET_Data_Charting_1.2.py.
"""

import csv
import glob
import os
import re
import sys
from datetime import date

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

DEVICE_ID_RE = re.compile(r"^\d{8}$")


def find_source_file(folder, suffix):
    matches = glob.glob(os.path.join(folder, f"*{suffix}"))
    if not matches:
        matches = [f for f in glob.glob(os.path.join(folder, "*"))
                   if f.lower().endswith(suffix.lower())]
    if not matches:
        return None
    return sorted(matches, key=len)[0]


def extract_device_id(log_csv_path):
    with open(log_csv_path, "r", newline="", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "calib.json,deviceID," in line:
                candidate = line.strip().split(",")[-1].strip()
                if DEVICE_ID_RE.match(candidate):
                    return candidate
                raise ValueError(
                    f"Found a deviceID line but value '{candidate}' is not 8 digits")
    raise ValueError("No 'calib.json,deviceID,<8 digits>' line found in log.csv")


def csv_to_dataframe(path):
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if r]
    if not rows:
        return pd.DataFrame()

    max_fields = max(len(r) for r in rows)
    padded = [r + [""] * (max_fields - len(r)) for r in rows]

    columns = ["timestamp_epoch", "record_type"]
    columns += [f"field_{i}" for i in range(2, max_fields)]
    df = pd.DataFrame(padded, columns=columns)

    for col in df.columns:
        series = df[col]
        non_empty = series != ""
        if not non_empty.any():
            continue
        numeric = pd.to_numeric(series[non_empty], errors="coerce")
        if numeric.notna().all():
            df[col] = pd.to_numeric(series.replace("", None), errors="coerce")

    return df


def convert_folder(source_dir, dest_dir):
    """Convert one device folder's Sensor_Data.csv/log.csv to Parquet.

    Returns a list of human-readable result/error lines. Never modifies
    anything under source_dir.
    """
    messages = []

    log_path = find_source_file(source_dir, "log.csv")
    sensor_path = find_source_file(source_dir, "Sensor_Data.csv")

    if not log_path:
        messages.append("ERROR: no *log.csv file found in source folder.")
        return messages
    if not sensor_path:
        messages.append("ERROR: no *Sensor_Data.csv file found in source folder.")
        return messages

    try:
        device_id = extract_device_id(log_path)
    except ValueError as e:
        messages.append(f"ERROR: {e}")
        return messages
    messages.append(f"DeviceID: {device_id}")

    today = date.today().isoformat()

    for label, src_path, name_suffix in (
        ("Sensor_Data", sensor_path, "Sensor_Data"),
        ("Log", log_path, "Log"),
    ):
        try:
            df = csv_to_dataframe(src_path)
            out_name = f"{device_id}-{today}-{name_suffix}.parquet"
            out_path = os.path.join(dest_dir, out_name)
            df.to_parquet(out_path, engine="pyarrow", index=False)
            size_mb = os.path.getsize(out_path) / 1e6
            messages.append(
                f"OK: {os.path.basename(src_path)} -> {out_name} "
                f"({len(df):,} rows, {size_mb:.2f} MB)")
        except Exception as e:
            messages.append(f"ERROR converting {os.path.basename(src_path)}: {e}")

    return messages


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VEET CSV -> Parquet Converter")
        self.resize(640, 420)

        self.source_dir = None
        self.dest_dir = None

        central = QWidget()
        layout = QVBoxLayout(central)

        source_row = QHBoxLayout()
        self.source_label = QLabel("(no source folder selected)")
        self.source_label.setWordWrap(True)
        source_btn = QPushButton("Select Source Folder...")
        source_btn.clicked.connect(self.pick_source_folder)
        source_row.addWidget(source_btn)
        source_row.addWidget(self.source_label, stretch=1)
        layout.addLayout(source_row)

        dest_row = QHBoxLayout()
        self.dest_label = QLabel("(no output folder selected)")
        self.dest_label.setWordWrap(True)
        dest_btn = QPushButton("Select Output Folder...")
        dest_btn.clicked.connect(self.pick_dest_folder)
        dest_row.addWidget(dest_btn)
        dest_row.addWidget(self.dest_label, stretch=1)
        layout.addLayout(dest_row)

        self.convert_btn = QPushButton("Convert")
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self.run_conversion)
        layout.addWidget(self.convert_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        self.setCentralWidget(central)

    def pick_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder with Sensor_Data.csv / log.csv")
        if folder:
            self.source_dir = folder
            self.source_label.setText(folder)
            self.update_convert_enabled()

    def pick_dest_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder for Parquet files")
        if folder:
            self.dest_dir = folder
            self.dest_label.setText(folder)
            self.update_convert_enabled()

    def update_convert_enabled(self):
        self.convert_btn.setEnabled(bool(self.source_dir and self.dest_dir))

    def run_conversion(self):
        self.convert_btn.setEnabled(False)
        self.log.appendPlainText(f"--- Converting {self.source_dir} ---")
        QApplication.processEvents()
        try:
            messages = convert_folder(self.source_dir, self.dest_dir)
        except Exception as e:
            messages = [f"ERROR: unexpected failure: {e}"]
        for m in messages:
            self.log.appendPlainText(m)
        self.log.appendPlainText("")
        self.update_convert_enabled()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
