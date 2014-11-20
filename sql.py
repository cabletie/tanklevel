#!/usr/bin/python
# -*- coding: utf-8 -*-

import sqlite3
import sys
import csv

dbName = "adcpiv2.db"
tableName = "adcpiv2"

con = sqlite3.connect(dbName)

with con:
    
    cur = con.cursor()    
    
    cur.executescript("""
        DROP TABLE IF EXISTS adcpiv2;
        DROP TABLE IF EXISTS tmpTable;
        CREATE TABLE IF NOT EXISTS adcpiv2(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
        CREATE TABLE IF NOT EXISTS tmpTable(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
        """)
#.mode csv 
#.import rawdata.csv tmpTable

reader = csv.reader(open('rawdata.csv', 'r'), delimiter=',')
for row in reader:
  to_db = [unicode(row[0], "utf8"), unicode(row[1], "utf8"), unicode(row[2], "utf8")]
  cur.execute("INSERT INTO tmpTable(DateTime, Voltage, AdcChannel) VALUES (?, ?, ?);", to_db)
con.commit()
with con:
    cur = con.cursor()    
    cur.execute("INSERT INTO adcpiv2(DateTime, Voltage, AdcChannel) SELECT * FROM tmpTable;")
