DROP TABLE IF EXISTS adcpiv2;
DROP TABLE IF EXISTS tmpTable;
CREATE TABLE IF NOT EXISTS adcpiv2(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
CREATE TABLE IF NOT EXISTS tmpTable(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
.mode csv 
.import rawdata.csv tmpTable
INSERT INTO adcpiv2(DateTime, Voltage, AdcChannel) SELECT * FROM tmpTable;
