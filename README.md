# veet-csv-to-parquet

Standalone GUI utility that converts the two raw files a VEET device writes
(`Sensor_Data.csv`, `log.csv`) into Parquet, without altering the originals.

Parquet is an open, columnar, self-describing format with native readers in
pandas (`pd.read_parquet`), R (`arrow::read_parquet`), and MATLAB
(`parquetread`) — no custom binary unpacker required, and typically a much
smaller footprint than the raw CSVs for long (multi-day/multi-week)
collections.

## Usage

```
pip install -r requirements.txt
python veet_csv_to_parquet.py
```

1. Select the source folder containing `Sensor_Data.csv` and `log.csv`.
2. Select an output folder for the Parquet files.
3. Click Convert. Output files are named `{DeviceID}-{yyyy-mm-dd}-Sensor_Data.parquet`
   and `{DeviceID}-{yyyy-mm-dd}-Log.parquet`, where the date is the conversion
   date and the DeviceID is the 8-digit ID read from `log.csv`
   (`calib.json,deviceID,<8 digits>`).
4. The window stays open, so you can repeat with additional device folders.

Originals are never modified or deleted.

## Format notes

Both source files are heterogeneous logs — every line is
`epoch_timestamp, TAG, field..., field...` with a different field count per
`TAG`, and no header row. Rows are transcribed generically (padded to the
widest row in the file, columns named `timestamp_epoch`, `record_type`,
`field_2`, `field_3`, ...) rather than re-derived per sensor type, so the
conversion is a faithful, lossless CSV → Parquet transcription rather than a
schema-aware reinterpretation of the sensor data.
