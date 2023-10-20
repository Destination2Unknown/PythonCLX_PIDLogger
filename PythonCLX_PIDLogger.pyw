import time
from datetime import datetime
import csv
import os
import threading
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
import customtkinter as ctk
from pylogix import PLC


class PeriodicInterval(threading.Thread):
    """
    A class for running a task function periodically at a specified interval.
    """

    def __init__(self, task_function, period):
        """
        Initialize the PeriodicInterval thread.
        """
        super().__init__()
        self.daemon = True
        self.task_function = task_function
        self.period = period
        self.i = 0
        self.t0 = time.time()
        self.stop_event = threading.Event()
        self.locker = threading.Lock()
        self.start()

    def sleep(self):
        """
        Sleep for the remaining time to meet the specified period.
        """
        self.i += 1
        delta = self.t0 + self.period * self.i - time.time()
        if delta > 0:
            time.sleep(delta)

    def run(self):
        """
        Start the thread and execute the task_function periodically.
        """
        while not self.stop_event.is_set():
            with self.locker:
                self.task_function()
            self.sleep()

    def stop(self):
        """
        Set the stop event to terminate the periodic task execution.
        """
        self.stop_event.set()


class CLX_PID_Logger(object):
    def __init__(self):
        # Initialize the PLC communication and set up the GUI
        self.comm = PLC()
        self.gui_setup()
        self.reset()

    def gui_setup(self):
        # Set up the graphical user interface (GUI) elements
        self.root = ctk.CTk()
        self.root.title("CLX PID Data Logger -> CSV")
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.offset = 7
        self.toolbar = 73

        # Configure GUI window size and appearance
        self.root.resizable(True, True)
        self.root.geometry(f"{int(self.screen_width/2)}x{self.screen_height-self.toolbar}+{-self.offset}+0")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(expand=True, fill=ctk.BOTH)

        # Define various variables to be used in the GUI
        self.sp_value = ctk.DoubleVar()
        self.pv_value = ctk.DoubleVar()
        self.cv_value = ctk.DoubleVar()

        self.read_count = ctk.IntVar()
        self.error_count = ctk.IntVar()
        self.gui_status = ctk.StringVar()

        self.sp_plc_tag = ctk.StringVar(value="SP")
        self.pv_plc_tag = ctk.StringVar(value="PID_PV")
        self.cv_plc_tag = ctk.StringVar(value="PID_CV")

        self.sp_write_value = ctk.StringVar()
        self.cv_write_value = ctk.StringVar()

        self.ip_address = ctk.StringVar(value="192.168.123.100")
        self.slot = ctk.IntVar(value=2)

        self.delta_t = ctk.DoubleVar(value=100)
        self.file_name = ctk.StringVar(value="D:\Trend.csv")

        # Column 0: Labels
        ctk.CTkLabel(self.main_frame, text="Tag").grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, text="SP:").grid(row=1, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, text="PV:").grid(row=2, column=0, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, text="CV:").grid(row=3, column=0, padx=10, pady=10)

        # Column 1: PLC Tags
        ctk.CTkLabel(self.main_frame, text="PLC Tag").grid(row=0, column=1, padx=10, pady=10)
        self.entry_sp_tag = ctk.CTkEntry(self.main_frame, textvariable=self.sp_plc_tag)
        self.entry_sp_tag.grid(row=1, column=1, padx=10, pady=10, sticky=ctk.NSEW)
        self.entry_pv_tag = ctk.CTkEntry(self.main_frame, textvariable=self.pv_plc_tag)
        self.entry_pv_tag.grid(row=2, column=1, padx=10, pady=10, sticky=ctk.NSEW)
        self.entry_cv_tag = ctk.CTkEntry(self.main_frame, textvariable=self.cv_plc_tag)
        self.entry_cv_tag.grid(row=3, column=1, padx=10, pady=10, sticky=ctk.NSEW)

        # Column 2: Actual Values
        ctk.CTkLabel(self.main_frame, text="      Value      ").grid(row=0, column=2, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, textvariable=self.sp_value).grid(row=1, column=2, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, textvariable=self.pv_value).grid(row=2, column=2, padx=10, pady=10)
        ctk.CTkLabel(self.main_frame, textvariable=self.cv_value).grid(row=3, column=2, padx=10, pady=10)

        # Column 4: Send - Write Values
        ctk.CTkLabel(self.main_frame, text="Write to PLC").grid(row=0, column=4, padx=10, pady=10, sticky=ctk.NSEW)
        self.entry_sp_write = ctk.CTkEntry(self.main_frame, textvariable=self.sp_write_value)
        self.entry_sp_write.grid(row=1, column=4, padx=10, pady=10, sticky=ctk.NSEW)
        self.entry_cv_write = ctk.CTkEntry(self.main_frame, textvariable=self.cv_write_value)
        self.entry_cv_write.grid(row=3, column=4, padx=10, pady=10, sticky=ctk.NSEW)

        # Buttons
        self.button_record = ctk.CTkButton(self.main_frame, text="Record Data", command=lambda: [self.record_data()])
        self.button_record.grid(row=4, column=1, columnspan=2, padx=10, pady=10, sticky=ctk.NSEW)

        self.button_livetrend = ctk.CTkButton(self.main_frame, text="Live Plot", command=lambda: [self.show_live_trend()])
        self.button_livetrend.grid(row=4, column=3, columnspan=1, padx=10, pady=10, sticky=ctk.NSEW)
        self.button_livetrend.configure(state=ctk.DISABLED)

        self.button_write = ctk.CTkButton(self.main_frame, text="Write", command=lambda: [self.write_to_PLC()])
        self.button_write.grid(row=4, column=4, columnspan=1, padx=10, pady=10, sticky=ctk.NSEW)

        self.button_stop = ctk.CTkButton(self.main_frame, text="Stop Recording", command=lambda: [self.stop()])
        self.button_stop.grid(row=5, column=1, columnspan=3, padx=10, pady=10, sticky=ctk.NSEW)
        self.button_stop.configure(state=ctk.DISABLED)

        self.button_show_file_data = ctk.CTkButton(self.main_frame, text="Plot Data From CSV", command=lambda: [self.open_trend_from_file()])
        self.button_show_file_data.grid(row=5, column=4, columnspan=1, padx=10, pady=10, sticky=ctk.NSEW)

        ctk.CTkLabel(self.main_frame, text="").grid(row=6, column=0, padx=10, pady=10)
        # Settings
        ctk.CTkLabel(self.main_frame, text="PLC IP Address:").grid(row=7, column=0, padx=10, pady=10)
        self.entry_ip = ctk.CTkEntry(self.main_frame, textvariable=self.ip_address)
        self.entry_ip.grid(row=7, column=1, padx=10, pady=10, sticky=ctk.NSEW)

        ctk.CTkLabel(self.main_frame, text="PLC Slot:").grid(row=8, column=0, padx=10, pady=10)
        self.entry_slot = ctk.CTkEntry(self.main_frame, textvariable=self.slot, width=60)
        self.entry_slot.grid(row=8, column=1, padx=10, pady=10, sticky=ctk.W)

        ctk.CTkLabel(self.main_frame, text="Interval (mS):").grid(row=9, column=0, padx=10, pady=10)
        self.entry_delta_t = ctk.CTkEntry(self.main_frame, textvariable=self.delta_t, width=60)
        self.entry_delta_t.grid(row=9, column=1, columnspan=1, padx=10, pady=10, sticky=ctk.W)

        ctk.CTkLabel(self.main_frame, text="File Name:").grid(row=10, column=0, padx=10, pady=10)
        self.entry_file_name = ctk.CTkEntry(self.main_frame, textvariable=self.file_name)
        self.entry_file_name.grid(row=10, column=1, columnspan=3, padx=10, pady=10, sticky=ctk.NSEW)

        ctk.CTkLabel(self.main_frame, text="Read Count:").grid(row=11, column=0, padx=10, pady=10, sticky=ctk.NSEW)
        ctk.CTkLabel(self.main_frame, textvariable=self.read_count).grid(row=11, column=1, padx=10, pady=10, sticky=ctk.W)

        ctk.CTkLabel(self.main_frame, text="Error Count:").grid(row=12, column=0, padx=10, pady=10, sticky=ctk.NSEW)
        ctk.CTkLabel(self.main_frame, textvariable=self.error_count).grid(row=12, column=1, padx=10, pady=10, sticky=ctk.W)

        ctk.CTkLabel(self.main_frame, text="Status:").grid(row=13, column=0, padx=10, pady=10, sticky=ctk.NSEW)
        ctk.CTkLabel(self.main_frame, textvariable=self.gui_status).grid(row=13, column=1, columnspan=5, padx=10, pady=10, sticky=ctk.W)

    def reset(self):
        # Reset various variables and data arrays
        self.PV = np.zeros(0)
        self.CV = np.zeros(0)
        self.SP = np.zeros(0)
        self.record_loop = None
        self.CSVFile = None
        self.CSVFileWriter = None
        self.comm_write = None
        self.anim = None

    def record_data(self):
        try:
            # Perform pre-flight checks and start recording data
            self.pre_flight_checks()
            self.record_loop = PeriodicInterval(self.get_data, int(self.delta_t.get()) / 1000)
        except Exception as e:
            self.gui_status.set(str(e))
        else:
            self.live_trend()

    def pre_flight_checks(self):
        # Check PLC communication settings and prepare for recording
        self.tag_list = [self.sp_plc_tag.get(), self.pv_plc_tag.get(), self.cv_plc_tag.get()]
        self.comm.IPAddress = self.ip_address.get()
        self.comm.ProcessorSlot = self.slot.get()
        self.comm.SocketTimeout = 10.0

        self.gui_status.set("")
        self.error_count.set(0)
        self.read_count.set(0)

        self.CSVFile = open(self.file_name.get(), "a")
        self.CSVFileWriter = csv.writer(self.CSVFile, delimiter=";", lineterminator="\n", quotechar="/", quoting=csv.QUOTE_MINIMAL)
        if os.stat(self.file_name.get()).st_size == 0:
            self.CSVFileWriter.writerow(("SP", "PV", "CV", "TimeStamp"))
        ret = self.comm.Read(self.tag_list)

        if any(x.Value is None for x in ret):
            raise Exception("Check Configuration")
        else:
            self.button_stop.configure(state=ctk.NORMAL)
            self.button_record.configure(state=ctk.DISABLED)
            self.gui_inputs_state(req_state=ctk.DISABLED)

        self.comm.SocketTimeout = sorted([0.1, self.delta_t.get() * 1.1 / 1000, 5.0])[1]

    def get_data(self):
        try:
            # Read data from PLC, update GUI, and write to CSV
            ret = self.comm.Read(self.tag_list)
            ret_values = [x.Value for x in ret]
            ret_states = [x.Status for x in ret]
            gui_tags = [self.sp_value, self.pv_value, self.cv_value]

            for i in range(len(ret_values)):
                if ret_states[i] == "Success":
                    gui_tags[i].set(round(ret_values[i], 3))
                else:
                    self.gui_status.set(ret_states[i])

            self.SP = np.append(self.SP, ret_values[0])
            self.PV = np.append(self.PV, ret_values[1])
            self.CV = np.append(self.CV, ret_values[2])

            current_date_time = datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S.%f")
            csv_values = ret_values + [current_date_time]

            self.CSVFileWriter.writerow(csv_values)
            success_count = sum(1 for x in ret_states if x == "Success")
            error_count = len(ret) - success_count
            self.read_count.set(self.read_count.get() + success_count)
            self.error_count.set(self.error_count.get() + error_count)

        except Exception as e:
            self.gui_status.set("Error: " + str(e))

    def write_to_PLC(self):
        if self.sp_write_value.get() == "" and self.cv_write_value.get() == "":
            self.gui_status.set("No Values to Write")
            return

        try:
            # Write values to the PLC
            if not self.comm_write:
                self.comm_write = PLC()
                self.comm_write.IPAddress = self.ip_address.get()
                self.comm_write.ProcessorSlot = self.slot.get()
                self.comm_write.SocketTimeout = 1

            if self.sp_write_value.get() != "":
                sp = float(self.sp_write_value.get())
                ret = self.comm_write.Write(self.sp_plc_tag.get(), sp)
                if ret.Status == "Success":
                    self.sp_value.set(round(ret.Value, 3))
                else:
                    raise Exception(ret.TagName + " " + ret.Status)

            if self.cv_write_value.get() != "":
                cv = float(self.cv_write_value.get())
                ret = self.comm_write.Write(self.cv_plc_tag.get(), cv)
                if ret.Status == "Success":
                    self.cv_value.set(round(ret.Value, 3))
                else:
                    raise Exception(ret.TagName + " " + ret.Status)

        except Exception as e:
            self.gui_status.set("Write Error: " + str(e))

        else:
            self.gui_status.set("Data sent to PLC")

        finally:
            self.comm_write.Close()

    def open_trend_from_file(self):
        try:
            if self.record_loop:
                self.CSVFile.flush()
            df = pd.read_csv(self.file_name.get(), sep=";", quoting=csv.QUOTE_NONE, escapechar="\\", encoding="utf-8")
            headers = list(df)
            df["TimeStamp"] = pd.to_datetime(df["TimeStamp"], format="%d-%m-%Y %H:%M:%S.%f")

            # Set Plot location on screen
            plt.figure()
            mngr = plt.get_current_fig_manager()
            mngr.window.geometry(f"{int(self.screen_width/2)}x{self.screen_height-self.toolbar}+{int(self.screen_width/2)-self.offset}+0")
            # Generate Plot
            plt.plot(df["TimeStamp"], df[headers[0]], color="#1f77b4", linewidth=2, label=headers[0])
            plt.plot(df["TimeStamp"], df[headers[1]], color="#ff7f0e", linewidth=2, label=headers[1])
            plt.plot(df["TimeStamp"], df[headers[2]], color="#2ca02c", linewidth=2, label=headers[2])
            plt.ylabel("Value")
            plt.xlabel("Time")
            plt.title(self.file_name.get())
            plt.legend(loc="upper right")
            plt.gcf().autofmt_xdate()
            plt.show()
        except Exception as e:
            self.gui_status.set("CSV Read Error: " + str(e))

    def live_trend(self):
        # Set up a live trend plot
        fig = plt.figure()
        self.ax = plt.axes()
        (SP,) = self.ax.plot([], [], lw=2, label="SP")
        (PV,) = self.ax.plot([], [], lw=2, label="PV")
        (CV,) = self.ax.plot([], [], lw=2, label="CV")

        def init():
            SP.set_data([], [])
            PV.set_data([], [])
            CV.set_data([], [])
            plt.ylabel("Value")
            plt.xlabel("Time (Minutes)")
            plt.suptitle("Live Data")
            plt.legend(loc="upper right")
            self.scale = int(60000 / int(self.delta_t.get()))  # Convert mS to Minutes

        def animate(i):
            try:
                x = np.arange(len(self.SP), dtype=int)
                x = x / self.scale
                SP.set_data(x, self.SP)
                CV.set_data(x, self.CV)
                PV.set_data(x, self.PV)
                self.ax.relim()
                self.ax.autoscale_view()
            except:
                pass

        self.anim = animation.FuncAnimation(fig, animate, init_func=init, frames=60, interval=1000)

        mngr = plt.get_current_fig_manager()
        mngr.window.geometry(f"{int(self.screen_width/2)}x{self.screen_height-self.toolbar}+{int(self.screen_width/2)-self.offset+1}+0")
        plt.gcf().canvas.mpl_connect("close_event", self.on_plot_close)
        plt.show()

    def on_plot_close(self, event):
        if self.record_loop:
            self.button_livetrend.configure(state=ctk.NORMAL)

    def show_live_trend(self):
        self.button_livetrend.configure(state=ctk.DISABLED)
        open_plots = plt.get_fignums()
        if len(open_plots) == 0:
            self.live_trend()

    def gui_inputs_state(self, req_state):
        # Control the state of GUI input elements
        self.entry_sp_tag.configure(state=req_state)
        self.entry_pv_tag.configure(state=req_state)
        self.entry_cv_tag.configure(state=req_state)
        self.entry_delta_t.configure(state=req_state)
        self.entry_ip.configure(state=req_state)
        self.entry_slot.configure(state=req_state)
        self.entry_file_name.configure(state=req_state)

    def stop(self):
        try:
            # Stop data recording, reset GUI elements, and close files
            if self.record_loop:
                self.record_loop.stop()
                self.record_loop = None
                time.sleep(self.delta_t.get() / 1000)

            self.gui_inputs_state(req_state=ctk.NORMAL)
            self.button_livetrend.configure(state=ctk.DISABLED)
            self.button_record.configure(state=ctk.NORMAL)

            if self.CSVFile:
                if not self.CSVFile.closed:
                    self.CSVFile.close()

            self.anim = None
            self.comm.Close()
            plt.close("all")
            self.reset()

        except Exception as e:
            self.gui_status.set("Stop Error: " + str(e))

        else:
            self.button_stop.configure(state=ctk.DISABLED)


if __name__ == "__main__":
    gui_app = CLX_PID_Logger()
    gui_app.root.mainloop()
