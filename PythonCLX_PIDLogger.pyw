import sys
import time
import tkinter as tk
import csv
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from datetime import datetime
from pylogix import PLC

class data(object):
    def __init__(self):      
        """Setup
        """
        self.pltPV = np.zeros(0)
        self.pltCV = np.zeros(0)
        self.pltSP = np.zeros(0)
        self.RunNow=0
        self.ErrCount=0
        self.ReadCount=0
        self.lastSP=0
        self.lastCV=0
        self.lastPV=0

    def update(self,PV,CV,SP):
        """Add Data 
        """
        self.pltPV=np.append(self.pltPV,PV)
        self.pltCV=np.append(self.pltCV,CV)
        self.pltSP=np.append(self.pltSP,SP) 
    
    def getlast(self):
        """returns last value when read fails
        """
        if len(self.pltPV)>0:
            self.lastPV=self.pltPV[-1]
            self.lastCV=self.pltCV[-1]
            self.lastSP=self.pltSP[-1] 

        return [self.lastPV,self.lastCV,self.lastSP]
        
    def reset(self):
        """Reset
        """
        self.pltPV = np.zeros(0)
        self.pltCV = np.zeros(0)
        self.pltSP = np.zeros(0)        
        self.RunNow=0
        
def Record():
    #Setup communnication object       
    comm.IPAddress = ip.get()
    comm.ProcessorSlot = int(slot.get())
    current_date_time = datetime.utcnow().strftime('%d-%m-%Y %H:%M:%S.%f')

    #Setup tags to read
    tag_list = [pvtexttag.get(), cvtexttag.get(), sptexttag.get()]
    ret = comm.Read(tag_list)
  
    #Update gui data if read is successful, if not update last error
    if ret[0].Status=='Success':
        pvtext.set(round(ret[0].Value,2))         
        pvtexttag.configure(state="disabled")
    else:
        pvstatus.set(ret[0].Status)

    #Update gui data if read is successful, if not update last error
    if ret[1].Status=='Success':
        cvtext.set(round(ret[1].Value,2))         
        cvtexttag.configure(state="disabled")
    else:
        cvstatus.set(ret[1].Status)

    #Update gui data if read is successful, if not update last error
    if ret[2].Status=='Success':
        sptext.set(round(ret[2].Value,2))
        sptexttag.configure(state="disabled")
    else:
        spstatus.set(ret[2].Status)

    #If read fails update error counter, if successful increment read counter
    if ret[0].Status=='Success' or ret[1].Status=='Success' or ret[2].Status=='Success':
        GData.ReadCount+=1
    if ret[0].Status!='Success' and ret[1].Status!='Success' and ret[2].Status!='Success':
        GData.ErrCount+=1
    ec='Errors: '+ str(GData.ErrCount)
    rc='Reads: '+ str(GData.ReadCount)
    errorcount.set(ec)
    readcount.set(rc)
    
    #Disable inputs if tag read is successful
    if ret[0].Status=='Success' or ret[1].Status=='Success' or ret[2].Status=='Success':
        deltat.configure(state="disabled")
        ip.configure(state="disabled")
        slot.configure(state="disabled")
        fname.configure(state="disabled")
        button_record.configure(bg = "Green")
        button_livetrend["state"] = "normal"

    #Write new data to csv if read was successful
    #if not write last value
    #Open File or create if it doesn't exist
    with open(fname.get(), 'a') as csv_file:
        csv_file = csv.writer(csv_file, delimiter=';', lineterminator='\n', quotechar='/', quoting=csv.QUOTE_MINIMAL)
        #Write headers if its a new file
        if os.stat(fname.get()).st_size == 0:
            csv_file.writerow((ret[0].TagName,ret[1].TagName,ret[2].TagName,'TimeStamp'))
        #Write all values to csv file  
        if ret[0].Status=='Success' or ret[1].Status=='Success' or ret[2].Status=='Success':  
            GData.update(ret[0].Value,ret[1].Value,ret[2].Value)
            row = [x.Value for x in ret]            
        else:
            #if read fails log last value
            GData.update(*GData.getlast())
            row = GData.getlast()        
        row.append(current_date_time)
        csv_file.writerow(row)

    #Loop       
    looper=root.after(int(deltat.get()), Record)
    #Stop when RunNow is false
    if not GData.RunNow:
        comm.Close()
        root.after_cancel(looper)
        #Enable text box entry
        sptexttag.configure(state="normal")
        pvtexttag.configure(state="normal")
        cvtexttag.configure(state="normal")
        deltat.configure(state="normal")
        ip.configure(state="normal")
        slot.configure(state="normal")
        fname.configure(state="normal")        
        button_record.configure(bg = "#f0f0f0")
        button_livetrend["state"] = "disabled"
          
def Write():
    #Setup comms
    comms = PLC()   
    comms.IPAddress = ip.get()
    comms.ProcessorSlot = int(slot.get())

    #Setup tags to read back data
    tag_list = [cvtexttag.get(), sptexttag.get()]    
    
    #Don't write data if empty, reads back data after write
    if spsend.get(): 
        sp = float(spsend.get())    
        comms.Write(sptexttag.get(), sp)              
        sptext.set(round(comms.Read(sptexttag.get()).Value,2)) 
    if cvsend.get():
        cv=float(cvsend.get())
        comms.Write(cvtexttag.get(), cv)
        cvtext.set(round(comms.Read(cvtexttag.get()).Value,2))
    comms.Close()

def TrendFileData():
    df = pd.read_csv(fname.get(), sep=';',quoting=csv.QUOTE_NONE, escapechar="\\", encoding="utf-8")
    headers=list(df)
    df['TimeStamp'] = pd.to_datetime(df['TimeStamp'],format='%d-%m-%Y %H:%M:%S.%f')
    plt.figure()
    plt.plot(df['TimeStamp'],df[headers[0]], color="#1f77b4", linewidth=2, label=headers[0])
    plt.plot(df['TimeStamp'],df[headers[1]], color="#ff7f0e",linewidth=2,label=headers[1])
    plt.plot(df['TimeStamp'],df[headers[2]], color="#2ca02c",linewidth=2,label=headers[2])
    plt.ylabel('EU')                   
    plt.xlabel("Time")
    plt.title(fname.get())
    plt.legend(loc='best')
    plt.gcf().autofmt_xdate()
    plt.show()
 
def LiveTrend(): 
    #Set up the figure
    fig = plt.figure()
    ax = plt.axes(xlim=(0,100),ylim=(0, 100))
    SP, = ax.plot([], [], lw=2, label='SP')
    PV, = ax.plot([], [], lw=2, label='PV')
    CV, = ax.plot([], [], lw=2, label='CV')

    #Setup Func
    def init():
        SP.set_data([], [])
        PV.set_data([], [])
        CV.set_data([], [])
        plt.ylabel('EU')  
        plt.xlabel("Time (min)")
        plt.suptitle("Live Data")        
        plt.legend(loc='best')
        return SP,PV,CV,

    #Loop here
    def animate(i):     
        x = np.arange(len(GData.pltSP),dtype=int)
        scale = int(60*1000/int(deltat.get())) #Convert mS to Minutes
        x=x/scale
        ax.set_xlim(0,max(x)*1.1)
        SP.set_data(x,GData.pltSP)
        CV.set_data(x,GData.pltCV)
        PV.set_data(x,GData.pltPV)
        return SP,PV,CV,

    #Live Data
    if GData.RunNow:
        anim = animation.FuncAnimation(fig, animate, init_func=init, frames=100, interval=1000) #, blit=True) # cant use blit with dynamic x-axis

    plt.show()
   
def Start():      
    spstatus.set("")
    pvstatus.set("")
    cvstatus.set("")
    GData.RunNow=1 
    GData.ErrCount=0
    GData.ReadCount=0

def Close():    
    GData.reset()
    plt.close('all')

#Gui
root = tk.Tk()
root.title('CLX PID Data Logger -> CSV')
root.resizable(True, True)
root.geometry('510x175')

#Text tags setup
pvtext = tk.StringVar()
cvtext = tk.StringVar()
sptext = tk.StringVar()
pvstatus = tk.StringVar()
cvstatus = tk.StringVar()
spstatus = tk.StringVar()
errorcount = tk.StringVar()
readcount = tk.StringVar()
sptexttag = tk.Entry(root,width=10)
pvtexttag = tk.Entry(root,width=10)
cvtexttag = tk.Entry(root,width=10)
spsend = tk.Entry(root,width=5)
cvsend = tk.Entry(root,width=5)
deltat = tk.Entry(root,width=5)
ip = tk.Entry(root,width=15)
slot = tk.Entry(root,width=5)
fname = tk.Entry(root,width=5)

#Column 0
#Labels
tk.Label(root, text="  ").grid(row=0,column=0,padx=10 ,pady=2)
tk.Label(root, text="Tag").grid(row=0,column=0,padx=10 ,pady=2)
tk.Label(root, text="SP:").grid(row=1,column=0,padx=10 ,pady=2)
tk.Label(root, text="PV:").grid(row=2,column=0,padx=10 ,pady=2)
tk.Label(root, text="CV:").grid(row=3,column=0,padx=10 ,pady=2)

#Column 1
#Label positions - Read
tk.Label(root, text="Value").grid(row=0,column=1,padx=10 ,pady=2)
tk.Label(root, textvariable=sptext).grid(row=1,column=1,padx=10 ,pady=2)
tk.Label(root, textvariable=pvtext).grid(row=2,column=1,padx=10 ,pady=2)
tk.Label(root, textvariable=cvtext).grid(row=3,column=1,padx=10 ,pady=2)

#Column 2
#Send - Write
tk.Label(root, text="Write").grid(row=0,column=2,padx=10 ,pady=2)
spsend.grid(row=1, column=2,padx=10 ,pady=2,sticky="NESW")
cvsend.grid(row=3, column=2,padx=10 ,pady=2,sticky="NESW")

#Column 3
#Actual PLC TagName
tk.Label(root, text="PLC Tag").grid(row=0,column=3,padx=10 ,pady=2)
sptexttag.grid(row=1, column=3,padx=10 ,pady=2,sticky="NESW")
pvtexttag.grid(row=2, column=3,padx=10 ,pady=2,sticky="NESW")
cvtexttag.grid(row=3, column=3,padx=10 ,pady=2,sticky="NESW")
deltat.grid(row=4, column=3,columnspan=1,padx=10 ,pady=2,sticky="NESW")
tk.Label(root, text="mS",bg='#F0F0F0').grid(row=4,column=3,padx=10 ,pady=2,sticky="E")

#Column 4
#Actual PLC IP address
tk.Label(root, text="PLC IP Address:").grid(row=0,column=4,padx=10 ,pady=2)
ip.grid(row=1, column=4,padx=10 ,pady=2,sticky="NESW")
tk.Label(root, text="PLC Slot:").grid(row=2,column=4,padx=10 ,pady=2)
slot.grid(row=3, column=4,padx=10 ,pady=2,sticky="NESW")
fname.grid(row=4, column=4,padx=10 ,pady=2,sticky="NESW",columnspan=1)

#Column 5
#Status
tk.Label(root, text="Last Error:").grid(row=0,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")
tk.Label(root, textvariable=spstatus).grid(row=1,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")
tk.Label(root, textvariable=pvstatus).grid(row=2,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")
tk.Label(root, textvariable=cvstatus).grid(row=3,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")
tk.Label(root, textvariable=errorcount).grid(row=4,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")
tk.Label(root, textvariable=readcount).grid(row=5,column=5,padx=10,columnspan=2 ,pady=2,sticky="NESW")

#Default Values
sptexttag.insert(10, "SP")
pvtexttag.insert(10, "PID_PV")
cvtexttag.insert(10, "PID_CV")
deltat.insert(5, "100")
ip.insert(10, "192.168.123.100")
slot.insert(5, "2")
fname.insert(10,"D:\Trend.csv")

#Buttons
#Record Button Placement
button_record = tk.Button(root, text="Record Data", command=lambda :[Start(),Record()])
button_record.grid(row=4,column=0,columnspan=2,padx=10 ,pady=2,sticky="NESW")

#Write Button Placement
button_write = tk.Button(root, text="Write", command=lambda :[Write()])
button_write.grid(row=4,column=2,columnspan=1,padx=10 ,pady=2,sticky="NESW")

#Live Trend Button Placement
button_livetrend = tk.Button(root, text="Live Plot", command=lambda :[LiveTrend()])
button_livetrend.grid(row=5,column=3,columnspan=1,padx=10 ,pady=2,sticky="NESW")
button_livetrend["state"] = "disabled"

#Close Trends Button Placement
button_close = tk.Button(root, text="Stop Recording", command=lambda :[Close()])
button_close.grid(row=5,column=0,columnspan=3,padx=10 ,pady=2,sticky="NESW")

#Trend Button Placement
button_TrendFileData = tk.Button(root, text="Plot Data From CSV", command=lambda :[TrendFileData()])
button_TrendFileData.grid(row=5,column=4,columnspan=1,padx=10 ,pady=2,sticky="NESW")

#Class init
GData=data()
comm = PLC()

root.mainloop()