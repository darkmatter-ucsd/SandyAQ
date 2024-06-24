import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import sys
import glob
import os

import configparser
import json
import scipy.stats

import datetime
import pandas as pd

import util
import WaveformProcessor
import FitSPE
from matplotlib.lines import Line2D



sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

#### To do:
# More comments and documentation

class scalar_processed_data:
    def __init__(self):

        # print("Reading: ", config_name)
        # config_path = os.path.join(self.data_folder, "tmp",config_name)
        # config = configparser.ConfigParser()
        # config.optionxform = str
        # config.read(config_path)

        self.timestamp_str = ""
        self.datetime_obj = datetime.datetime(1970,1,1,1,1,1)
        self.channel = int(0)
        self.bias_voltage = -1.0
        self.n_events = int(0)
        self.integral_window = (0.0,0.0)

        self.process_config = {}
        self.start_index = int(0)
        self.end_index = int(0)
        self.n_processed_events = int(0)

        self.baseline_mean = 0.0
        self.baseline_std = 0.0
        self.threshold_adc = int(0)
        self.areas = 0.0
        self.heights = 0.0
        
        self.randomly_selected_raw_WF = np.array([])
        self.randomly_selected_filtered_WF = np.array([])

        self.hist_count = np.array([])
        self.bin_edges = np.array([])

    def convert_to_dict(self):
        return {"timestamp_str": self.timestamp_str, 
                "datetime_obj": self.datetime_obj, 
                "channel": self.channel, 
                "bias_voltage": self.bias_voltage, 
                "n_events": self.n_events, 
                "integral_window": self.integral_window, 
                "process_config": self.process_config, 
                "start_index": self.start_index, 
                "end_index": self.end_index, 
                "n_processed_events": self.n_processed_events, 
                "baseline_mean": self.baseline_mean, 
                "baseline_std": self.baseline_std, 
                "threshold_adc": int(self.threshold_adc), 
                "areas": self.areas, 
                "heights": self.heights, 
                "hist_count": self.hist_count, 
                "bin_edges": self.bin_edges,
                "randomly_selected_raw_WF": self.randomly_selected_raw_WF,
                "randomly_selected_filtered_WF": self.randomly_selected_filtered_WF}
    
class PostProcessing:
    def __init__(self,
                 data_folder, # path to the data folder 
                 list_of_files, 
                 ignore_channel_list = np.array([2,8,11,14,20,23]),
                 calibration_run = False):

        self.data_folder = data_folder
        self.list_of_files = list_of_files
        self.ignore_channel_list = ignore_channel_list
        self.calibration_run = calibration_run

        self.df = pd.DataFrame(columns = ["timestamp_str", "datetime_obj", "channel", "bias_voltage", 
                                          "n_events", "integral_window", "process_config", 
                                          "start_index", "end_index", "n_processed_events", 
                                          "baseline_mean", "baseline_std", "threshold_adc", 
                                          "areas", "heights","hist_count","bin_edges",
                                          "randomly_selected_raw_WF","randomly_selected_filtered_WF"]) 
        # self.df = pd.DataFrame({"timestamp_str":pd.Series([], dtype='str'), 
        #                         "datetime_obj":pd.Series([], dtype='object'), 
        #                         "channel":pd.Series([], dtype='int'),
        #                         "bias_voltage":pd.Series([], dtype='float'),
        #                         "n_events":pd.Series([], dtype='int'),
        #                         "integral_window":pd.Series([], dtype='float'),
        #                         "process_config":pd.Series([], dtype='str'),
        #                         "start_index":pd.Series([], dtype='int'),
        #                         "end_index":pd.Series([], dtype='int'),
        #                         "n_processed_events":pd.Series([], dtype='int'),
        #                         "baseline_mean":pd.Series([], dtype='float'),
        #                         "baseline_std":pd.Series([], dtype='float'),
        #                         "threshold_adc":pd.Series([], dtype='int'),
        #                         "areas":pd.Series([], dtype='float'),
        #                         "heights":pd.Series([], dtype='float'),                          
        #                         "randomly_selected_raw_WF":pd.Series([], dtype='object'),
        #                         "randomly_selected_filtered_WF":pd.Series([], dtype='object')}) 
                
        #plot settings
        self.fontsize = "small"  
        
    def process_run(self):
        self._v_process_run(self, self.list_of_files)
        return 
    
    def process_run_single_run(self, meta_data):

        spd = scalar_processed_data()

        # print(sorted_meta_data_list[i])
        # meta_data = sorted_meta_data_list[i]
        meta_data_basename = os.path.basename(meta_data)
        parts = meta_data_basename.split('_')
        
        config_name = "_".join(parts[1:4]) + ".ini"
        spd.threshold_adc = parts[3]
        spd.channel = int(parts[2])
        spd.timestamp_str = f"{int(parts[4])}_{int(parts[5].split('.')[0])}"

        spd.datetime_obj = datetime.datetime.strptime(f"{parts[4]} {parts[5].split('.')[0]}", '%Y%m%d %H%M%S')

        # ignore the channels that in the ignore_channel_list
        if spd.channel in self.ignore_channel_list: 
            return

        # read from meta data file
        with open(meta_data, "r") as f:
            data_taking_settings = json.load(f)

        spd.n_events = int(data_taking_settings["number_of_events"])
        spd.bias_voltage = float(data_taking_settings["voltage_config"]["preamp_1"]) # assuming all preamp has the same bias voltage; can be easily changed
        # bias_voltage_list.append(bias_voltage)

        print("Reading: ", config_name)
        config_path = os.path.join(self.data_folder, "tmp",config_name)
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(config_path)

        spd.process_config = {"nchs": 1,
        "nsamps": int(config.get("COMMON", "RECORD_LENGTH")),
        "sample_selection": 120,
        "samples_to_average": 40}

        # dump the config to a json file
        with open("process_config.json", "w") as f:
            json.dump(spd.process_config, f)
            # set the board number and integral window according to the board number (board 0 and 1 have different integral windows)
        if len(config.get("BOARD-0", "CHANNEL_LIST")) > 0:
            board_number = 0
            # local_channel = channel
            spd.integral_window = (0.3,0.55)
        else:
            board_number = 1
            spd.integral_window = (0.3,0.55) #legacy, FIXME: remove
            # local_channel = channel - 16

        processor= sandpro.processing.rawdata.RawData(config_file = "process_config.json",
                                                perchannel=False)
        data_file_basename = meta_data_basename.replace("meta_", "").replace(".json", f"_board_{board_number}.bin")

        try:
            data = processor.get_rawdata_numpy(n_evts=spd.n_events-1,
                                        file=os.path.join(self.data_folder, data_file_basename),
                                        bit_of_daq=14,
                                        headersize=4,inversion=False)
            spd.start_index, spd.end_index = 2000, spd.n_events-1-500 #first 1000 events are noisy
            print(f"analysing events from range: {spd.start_index} to {spd.end_index}")
        except Exception as e:
            print(e)
            data = processor.get_rawdata_numpy(1999,
                                        file=os.path.join(self.data_folder, data_file_basename),
                                        bit_of_daq=14,
                                        headersize=4,inversion=False)
            spd.start_index, spd.end_index = 1000, 1999 #first 1000 events are noisy


        wfp = WaveformProcessor.WFProcessor(self.data_folder, volt_per_adc=2/2**14)
        wfp.set_data(data["data_per_channel"][spd.start_index:spd.end_index,0], in_adc = False)
        wfp.process_wfs()
        
        spd.baseline_std = np.mean(wfp.baseline_rms)
        spd.baseline_mean = np.mean(wfp.baseline)
        spd.n_processed_events = len(wfp.baseline_rms)

        spd.areas = wfp.get_area(sum_window=spd.integral_window)
        spd.heights = wfp.get_height(search_window=spd.integral_window)

        data_processed = data["data_per_channel"][spd.start_index:spd.end_index,0,:]
        mask = np.random.rand(spd.n_processed_events) < 0.05
        spd.randomly_selected_raw_WF = data_processed[mask,:]
        spd.randomly_selected_filtered_WF =  wfp.filtered_wfs[mask,:]
        # spd.hist_count,spd.bin_edges,_ = plt.hist(spd.areas,bins=200,range=(-0.1,10),histtype='step')
        spd.hist_count,spd.bin_edges = np.histogram(spd.areas,bins=200,range=(-0.1,10))
        plt.close()

        self.df.loc[len(self.df)] = spd.convert_to_dict()

        return

    _v_process_run = np.vectorize(process_run_single_run)
     
    def plot_waveforms(self, show_plot = False, save_plot = False, channels = []):

        if(len(self.df) == 0):
            print("No data to plot. Run process_run first.")
            return

        if len(channels) != 0:
            mask = self.df['channel'].isin(channels)
            df = self.df.loc[mask]
        else:
            df = self.df
        
        for i in range(len(df)):
            single_row_data = df.iloc[i]
            print(i)
            self.plot_waveform_single_run(spd = single_row_data, 
                                           show_plot = show_plot, 
                                           save_plot = save_plot)
            
        return
    
    def plot_waveform_single_run(self, spd, show_plot = False, save_plot = True):

        if not show_plot and not save_plot:
            raise ValueError("Cannot have both show_plot and save_plot as False")

        threshold_mv = util.adc_to_mv(int(spd.threshold_adc))
        # set the threshold to be 2 * Vpp
        optimal_threshold_mv =  (spd.baseline_mean + 2 * (2 * np.sqrt(2) * spd.baseline_std)) * 1000
        optimal_threshold_3sig_mv =  (spd.baseline_mean + 3 * spd.baseline_std) * 1000
        optimal_threshold_adc = util.mv_to_adc(optimal_threshold_mv)

        figure, axes = plt.subplots(3,2,figsize=(15,15))
        # figure.subplots_adjust(wspace=0.5)
        figure.subplots_adjust(hspace=0.3)
        time = np.arange(0, spd.process_config["nsamps"], 1) * 4

        randomly_selected_raw_WF = np.transpose(spd.randomly_selected_raw_WF)
        randomly_selected_filtered_WF = np.transpose(spd.randomly_selected_filtered_WF)
        
        axes[0,0].plot(time, 1000 * randomly_selected_raw_WF,color="red",alpha=0.2)
        axes[1,0].plot(time, 1000 * randomly_selected_raw_WF,color="red",alpha=0.2)
        axes[0,1].plot(time, 1000 * randomly_selected_filtered_WF,color="red",alpha=0.2)
        axes[1,1].plot(time, 1000 * randomly_selected_filtered_WF,color="red",alpha=0.2)
        
        axes[0,0].axhline(optimal_threshold_mv, linestyle = '--', color='g',label=f"Optimal threshold: \n{int(optimal_threshold_adc)}[ADC] \n{int(optimal_threshold_mv)}[mV]")
        axes[0,0].axhline(optimal_threshold_3sig_mv, linestyle = '-.', color='g',label=f"3 sig threshold: \n{int(optimal_threshold_3sig_mv)}[mV]")
        axes[0,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(spd.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[0,0].set_xlim(0,time[-1]-100)

        point_in_middle = time[int(len(time)/2)]
        axes[1,0].axhline(optimal_threshold_mv, linestyle = '--', color='g')
        axes[1,0].text(point_in_middle, optimal_threshold_mv, '~5 sigma', ha ='center', va ='center') 
        axes[1,0].axhline(optimal_threshold_3sig_mv, linestyle = '-.', color='g')
        axes[1,0].text(point_in_middle, optimal_threshold_3sig_mv, '3 sigma', ha ='center', va ='center') 
        axes[1,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(spd.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[1,0].set_xlim(0,time[-1]-100)

        _ymax = 1800
        axes[0,0].set_ylim(200,_ymax)
        axes[0,0].text(100,optimal_threshold_mv + _ymax/5,f"baseline mean: {1000 * spd.baseline_mean:.1f} mV")
        axes[0,0].text(100,optimal_threshold_mv + _ymax/10,f"baseline std: {1000 * spd.baseline_std:.2f} mV")
        axes[0,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,0].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[0,0].fill_betweenx([200,_ymax], spd.integral_window[0]*np.max(time), spd.integral_window[1]*np.max(time), color='gray', alpha=0.5)

        axes[0,1].set_xlim(0,time[-1]-100)
        axes[0,1].set_ylim(-5,1600)
        axes[0,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,1].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        
        _ymax = 350
        axes[1,0].set_xlim(0,time[-1]-100)
        axes[1,0].set_ylim(200,_ymax)
        axes[1,0].text(100,optimal_threshold_mv + _ymax/20,f"baseline mean: {1000 * spd.baseline_mean:.1f} mV")
        axes[1,0].text(100,optimal_threshold_mv + _ymax/40,f"baseline std: {1000 * spd.baseline_std:.2f} mV")
        axes[1,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,0].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[1,0].fill_betweenx([200,_ymax], spd.integral_window[0]*np.max(time), spd.integral_window[1]*np.max(time), color='gray', alpha=0.5)
        axes[1,0].axhline(1000 * spd.baseline_mean, color="gray",linestyle="dashed",label=f"Baseline mean", zorder=10)

        _ymax = 40
        axes[1,1].set_xlim(0,time[-1]-100)
        axes[1,1].set_ylim(-5,_ymax)
        axes[1,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,1].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)

        hist_count, bin_edges, _ = axes[2,0].hist(spd.areas,bins=200,range=(-0.1,10),histtype='step',color='red', label="Integrated area")
        axes[2,0].set_yscale("log")
        axes[2,0].set_ylabel("Count",fontsize=self.fontsize)
        axes[2,0].set_xlabel("Integrated Area [$V\cdot ns$]",fontsize=self.fontsize)
        axes[2,0].set_ylim(1e-1,None)

        if not self.calibration_run:
            try:
                spe_fit = FitSPE.FitSPE(hist_count, bin_edges, plot = False, show_plot=False, save_plot=False)
                axes[2,0].plot(np.transpose(spe_fit.line_x)[:,spe_fit.mu_err_list<0.03],np.transpose(spe_fit.line_y)[:,spe_fit.mu_err_list<0.03],color='black')
                axes[2,0].plot(np.transpose(spe_fit.line_x)[:,spe_fit.mu_err_list>=0.03],np.transpose(spe_fit.line_y)[:,spe_fit.mu_err_list>=0.03],color='blue')
            except:
                print("Could not fit SPE")

            handles, labels = axes[2,0].get_legend_handles_labels()
            custom_lines = [Line2D([0], [0], color='black'),
                            Line2D([0], [0], color='blue')]

            handles += custom_lines
            labels += ['Good fit','Bad fit']


        # axes[1,1].hist(heights,bins=100,range=(0,40),histtype='step')
        axes[2,1].hist2d(spd.areas,spd.heights,bins=[200,100],range=[[-0.1,10],[0,60]],cmap='viridis',norm="log")
        # axes[2,1].hist2d(spd.areas,spd.heights,bins=[200,100],cmap='viridis',norm="log",label="")
        axes[2,1].set_ylabel("Filtered Height [mV]",fontsize=self.fontsize)
        axes[2,1].set_xlabel("Filtered integrated area [$V\cdot ns$]",fontsize=self.fontsize)
        

        for ax in axes.flatten():
            if ax == axes[2,0]:
                # Update legend with custom lines and labels
                ax.legend(handles=handles, labels=labels,loc='upper right')
            else:
                ax.legend()
        axes[0,0].set_title(f"Raw WFs channel {spd.channel}")
        axes[0,1].set_title(f"Filtered WFs channel {spd.channel}")
        axes[1,0].set_title(f"Zoomed raw WFs channel {spd.channel}")
        axes[1,1].set_title(f"Zoomed filtered WFs channel {spd.channel}")
        axes[2,0].set_title(f"Integrated area distribution channel {spd.channel}")
        axes[2,1].set_title(f"Integrated area vs height channel {spd.channel}")

        figure_path = os.path.join(self.data_folder,"plot/")
        if not os.path.exists(figure_path):
                os.makedirs(figure_path)

        plt.legend(self.fontsize)
        if save_plot:
            plt.savefig(os.path.join(figure_path,f"plot_{spd.channel}_{spd.timestamp_str}.png"))
        
        plt.close()

        return
    
    def get_SPE(self, show_plot = False, save_plot = False, channels = []):
        if(len(self.df) == 0):
            print("No data to plot. Run process_run first.")
            return

        if len(channels) != 0:
            # select only the channels in the list
            mask = self.df['channel'].isin(channels)
            df = self.df.loc[mask]
        else:
            df = self.df

        spe_fit_list = []
        for i in range(len(df)):
            single_row_data = df.iloc[i]

            hist_count= np.array(single_row_data.hist_count)
            bin_edges = np.array(single_row_data.bin_edges)
            # try:
            spe_fit = FitSPE.FitSPE(hist_count, bin_edges, show_plot=show_plot, save_plot=save_plot)
            spe_fit_list.append(spe_fit)
            # except:
            #     print("Could not fit SPE")
            
        return spe_fit_list
    
        


        
