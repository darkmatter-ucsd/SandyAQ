import numpy as np
import matplotlib.pyplot as plt
import sys
import glob
import os

import configparser
import json
import scipy.stats
from scipy.optimize import curve_fit
import datetime
import pandas as pd

import util
import WaveformProcessor

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
                                          "areas", "heights", "randomly_selected_raw_WF", 
                                          "randomly_selected_filtered_WF"]) 
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
        
        
    def process_run(self, make_plot=False, show_plot=False):
        self._process_run(self, self.list_of_files, make_plot, show_plot)
        return 
    
    def plot_waveforms(self, show_plot = True, save_plot = False):
        if(len(self.df) == 0):
            print("No data to plot. Run process_run first.")
            return
        
        for i in range(len(self.df)):
            self._scalar_plot_waveforms(spd = self.df.iloc[i], 
                                        show_plot = show_plot, 
                                        save_plot = save_plot)
        return

    def _scalar_process_run(self, meta_data, make_plot = False, show_plot = False):

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

        # section_name = f"BOARD-{board_number}_CHANNEL-{local_channel}"
        # option_name = "N_EVENTS"
        # if config.has_option(section_name, option_name):
        # if n_events > :
            # n_events = int(config.get(section_name, option_name))
            # data = processor.get_rawdata_numpy(n_evts=int(n_events)-1,
            #                             file=os.path.join(data_folder, data_file_basename),
            #                             bit_of_daq=14,
            #                             headersize=4,inversion=False)
            # # start_index, end_index = 1500, 1980
            # start_index, end_index = 1000, int(n_events)-1
            # print(f"analysing events from {start_index} to {end_index}")
        # else:
        try:
            data = processor.get_rawdata_numpy(n_evts=spd.n_events-1,
                                        file=os.path.join(self.data_folder, data_file_basename),
                                        bit_of_daq=14,
                                        headersize=4,inversion=False)
            spd.start_index, spd.end_index = 1000, spd.n_events-1-500 #first 1000 events are noisy
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

        # baseline_mean_list.append(baseline_mean)
        # baseline_std_list.append(baseline_std)

        # print("number of events: ", len(wfp.baseline_rms))

        spd.areas = wfp.get_area(sum_window=spd.integral_window)
        spd.heights = wfp.get_height(search_window=spd.integral_window)

        data_processed = data["data_per_channel"][spd.start_index:spd.end_index,0,:]
        mask = np.random.rand(spd.n_processed_events) < 0.05
        spd.randomly_selected_raw_WF = data_processed[mask,:]
        spd.randomly_selected_filtered_WF =  wfp.filtered_wfs[mask,:]

        self.df.loc[len(self.df)] = spd.convert_to_dict()


        if make_plot:
            self._scalar_plot_waveforms(self, spd, show_plot = show_plot)

        return

    _process_run = np.vectorize(_scalar_process_run, excluded=['make_plot', 'show_plot'])

    def _scalar_plot_waveforms(self, spd, show_plot = True, save_plot = False):

        if not show_plot and not save_plot:
            raise ValueError("Cannot have both show_plot and save_plot as False")

        threshold_mv = util.adc_to_mv(int(spd.threshold_adc))
        # set the threshold to be 2 * Vpp
        optimal_threshold_mv =  (spd.baseline_mean + 2 * (2 * np.sqrt(2) * spd.baseline_std)) * 1000
        optimal_threshold_3sig_mv =  (spd.baseline_mean + 3 * spd.baseline_std) * 1000
        optimal_threshold_adc = util.mv_to_adc(optimal_threshold_mv)

        figure, axes = plt.subplots(3,2,figsize=(15,15))
        # figure.subplots_adjust(wspace=0.5)
        # figure.subplots_adjust(hspace=0.5)
        time = np.arange(0, spd.process_config["nsamps"], 1) * 4
        
        axes[0,0].plot(time, 1000 * np.transpose(spd.randomly_selected_raw_WF),color="red",alpha=0.2)
        axes[1,0].plot(time, 1000 * np.transpose(spd.randomly_selected_raw_WF),color="red",alpha=0.2)
        axes[0,1].plot(time, 1000 * np.transpose(spd.randomly_selected_filtered_WF),color="red",alpha=0.2)
        axes[1,1].plot(time, 1000 * np.transpose(spd.randomly_selected_filtered_WF),color="red",alpha=0.2)
        
        axes[0,0].axhline(optimal_threshold_mv, color='g',label=f"Optimal threshold: \n{int(optimal_threshold_adc)}[ADC] \n{int(optimal_threshold_mv)}[mV]")
        axes[0,0].axhline(optimal_threshold_3sig_mv, color='g',label=f"3 sig threshold: \n{int(optimal_threshold_mv)}[mV]")
        axes[0,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(spd.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[0,0].set_xlim(0,3900)

        axes[1,0].axhline(optimal_threshold_mv, color='g',label=f"Optimal threshold: \n{int(optimal_threshold_adc)}[ADC] \n{int(optimal_threshold_mv)}[mV]")
        axes[1,0].axhline(optimal_threshold_3sig_mv, color='g',label=f"3 sig threshold: \n{int(optimal_threshold_mv)}[mV]")
        axes[1,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(spd.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[1,0].set_xlim(0,3900)

        _ymax = 1800
        axes[0,0].set_ylim(200,_ymax)
        axes[0,0].text(100,optimal_threshold_mv + _ymax/5,f"baseline mean: {1000 * spd.baseline_mean:.1f} mV")
        axes[0,0].text(100,optimal_threshold_mv + _ymax/10,f"baseline std: {1000 * spd.baseline_std:.2f} mV")
        axes[0,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,0].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[0,0].fill_betweenx([200,_ymax], spd.integral_window[0]*np.max(time), spd.integral_window[1]*np.max(time), color='gray', alpha=0.5)

        axes[0,1].set_xlim(0,3900)
        axes[0,1].set_ylim(-5,1600)
        axes[0,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,1].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        
        _ymax = 350
        axes[1,0].set_xlim(0,3900)
        axes[1,0].set_ylim(200,_ymax)
        axes[1,0].text(100,optimal_threshold_mv + _ymax/20,f"baseline mean: {1000 * spd.baseline_mean:.1f} mV")
        axes[1,0].text(100,optimal_threshold_mv + _ymax/40,f"baseline std: {1000 * spd.baseline_std:.2f} mV")
        axes[1,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,0].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[1,0].fill_betweenx([200,_ymax], spd.integral_window[0]*np.max(time), spd.integral_window[1]*np.max(time), color='gray', alpha=0.5)
        axes[1,0].axhline(1000 * spd.baseline_mean, color="gray",linestyle="dashed",label=f"Baseline mean", zorder=10)


        _ymax = 40
        axes[1,1].set_xlim(0,3900)
        axes[1,1].set_ylim(-5,_ymax)
        axes[1,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,1].set_xlabel("ADC sample [ns]",fontsize=self.fontsize)

        hist,bin_edges,_ = axes[2,0].hist(spd.areas,bins=200,range=(-0.1,10),histtype='step',color='red')
        axes[2,0].set_yscale("log")
        axes[2,0].set_ylabel("Count",fontsize=self.fontsize)
        axes[2,0].set_xlabel("Integrated Area [$V\cdot ns$]",fontsize=self.fontsize)
        axes[2,0].set_ylim(1e-1,None)

        # axes[1,1].hist(heights,bins=100,range=(0,40),histtype='step')
        # axes[2,1].hist2d(areas,heights,bins=[200,100],range=[[-0.1,10],[0,40]],cmap='viridis',norm="log")
        axes[2,1].hist2d(spd.areas,spd.heights,bins=[200,100],cmap='viridis',norm="log")
        axes[2,1].set_ylabel("Filtered Height [mV]",fontsize=self.fontsize)
        axes[2,1].set_xlabel("Filtered integrated area [$V\cdot ns$]",fontsize=self.fontsize)
        
        for ax in axes.flatten():
            ax.legend()
        axes[0,0].set_title(f"Raw WFs channel {spd.channel}")
        axes[0,1].set_title(f"Filtered WFs channel {spd.channel}")


        # if not self.calibration_run:
        #     ##########finding the peak, and the specifit range###############
        #     hist_diff = np.diff(hist)  # Compute differences between consecutive histogram bins
        #     peaks = np.where((hist_diff[:-1] > 0) & (hist_diff[1:] < 0))[0] + 1  # Find indices where difference changes sign

        #     peak_indices = []
        #     hist_index=[]
        #     for peak_index in peaks:
        #         peak_indices.append(peak_index)
        #         hist_index.append(hist[peak_index])
        #         #axes[2, 0].plot(bin_edges[peak_index], hist[peak_index], marker='o', color='blue', markersize=8, label='Peak')


        #     edge1 = (bin_edges[peak_indices[0]]+bin_edges[peak_indices[1]])/2
        #     edge2 = (bin_edges[peak_indices[1]]+bin_edges[peak_indices[2]])/2
        #     edge3 = (bin_edges[peak_indices[2]]+bin_edges[peak_indices[3]])/2
        #     edge=[edge1,edge2,edge3]
        
            
        #     bin_width = bin_edges[1] - bin_edges[0]

        #     for k in edge:
        #         bin_index = int((k- bin_edges[0]) / bin_width)
        #         corresponding_count = hist[bin_index]
        #         axes[2,0].plot(k, corresponding_count, marker='o', color='blue', markersize=6, label='Peak')
            
        
        
        #     ##########adding the gaussian fit###############
        #     # Define the range of the specific part of the data you want to use for fitting
        #     pe=[]
        #     for j in range(len(edge)-1):
        #         specific_part_range = (edge[j],edge[j+1])
        #         specific_part_areas = [area for area in spd.areas if specific_part_range[0] <= area <= specific_part_range[1]]
        #         mu, sigma = scipy.stats.norm.fit(specific_part_areas)
        #         bins=np.linspace(-0.1, 10, 201)
        #         bins_subset = bins[(bins >= specific_part_range [0]) & (bins <= specific_part_range [1])]
                
        #         axes[2, 0].plot(bins_subset, scipy.stats.norm.pdf(bins_subset, mu, sigma), color='green', label='Gaussian Fit')

        #         min_y, max_y = axes[2, 0].get_ylim()
        #         axes[2, 0].vlines(mu, min_y, max_y, color='green', label='Gaussian Fit')

        #         pe.append(mu) # this line has the information of pe1 and pe2 for the gaussian fit

        #     ############ normalize it################
        #     # specific_hist, specific_bin_edges = np.histogram(specific_part_areas, bins=200, range=(edge1, edge2))

        
        #     # norm=np.sqrt(sum([i**2 for i in specific_part_areas]))
        #     # normalized=specific_hist/norm

        #     # bin_width = specific_part_areas[1] - specific_part_areas[0]

        #     # # Create the bar plot for the histogram
        #     # axes[2,0].bar(edge2, specific_hist, width=bin_width, edgecolor='black', alpha=0.7)
        
        #     #################################################################################################
        
        #     # mu_all_channel.append(pe)


        figure_path = os.path.join(self.data_folder,"plot/")
        if not os.path.exists(figure_path):
                os.makedirs(figure_path)

        plt.legend(self.fontsize)
        if save_plot:
            plt.savefig(os.path.join(figure_path,f"plot_{spd.channel}_{spd.timestamp_str}.png"))
        
        if show_plot:
            plt.show()

        return
      

    def fit_histograms(self, data_file, output_dir):
        # Load the data
        data = np.load(data_file)
        self.spd.load_data(data)

        # Fit the histograms
        self.spd.fit_histograms(output_dir)

