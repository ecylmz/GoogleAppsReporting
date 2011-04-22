#!/usr/bin/python
# -*- coding:utf-8 -*-

# Copyright ©, 2011 ecylmz :-P

import os
import csv
import datetime

def fetchReport(email, password, date, file):
    command = "python reporting.py --email=%s --password=%s --report=accounts --date=%s > %s" %(email, password, date, file)
    os.system(command)
    return file

def lastWeekControl(file):
    wList = whiteList()

    with open(file, "r") as file:
        rows = csv.reader(file)
        for row in rows:
            todayDate = row[0][:4] + "-" + row[0][4:6] + "-" + row[0][6:8]
            lastLoginDate = row[10][:4] + "-" + row[10][4:6] + "-" + row[10][6:8]
            if todayDate != "date--":
                yearDiff = int(todayDate[:4]) - int(lastLoginDate[:4])
                monthDiff = int(todayDate[5:7]) - int(lastLoginDate[5:7])
                dayDiff = int(todayDate[8:10]) - int(lastLoginDate[8:10])
                if ( yearDiff >= 1 or monthDiff >= 1 or dayDiff >= 6 ) and row[2] not in wList:
                    print "%s adlı kullanıcı son 1 haftadır giriş yapmadı..."%(row[2])

def whiteList():
    wList = []
    try:
        with open("whiteList.csv","r") as file:
            rows = csv.reader(file)
            for row in rows:
                wList.append(row[0])
    except:
        print "uyarı: whiteList.csv adında dosya olmadan işlem devam ediyor..."
    return wList

def main():
    email = 'admin@example.com'
    password = 'PaSsWoRd'
    date = datetime.date.today()
    file = 'data.csv'

    try:
        fetchReport(email, password, date, file)
        lastWeekControl(file)
    except:
        print "Hata oluştu,çıkıyorum..."

if __name__ == '__main__':
    main()
