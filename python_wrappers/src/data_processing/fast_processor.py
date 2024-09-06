import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm
import sys
import os
import glob


from dataclasses import dataclass

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.utils as util
import common.d2d as d2d
import data_processing.run_info as run_info
import data_processing.run_processor as run_processor
import gain_analysis.gain_processor as gain_processor
import data_processing.waveform_processor as waveform_processor
import common.config_reader as common_config_reader
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

#### To do:
# More comments and documentation
@dataclass
class FastInfo(run_info.RunInfo):
    
    def __init__(self):
        
        super().__init__()

        self.areas = np.nan
        self.heights = np.nan
        
        self.randomly_selected_raw_WF = np.array([])
        self.randomly_selected_filtered_WF = np.array([])

        self.hist_count = np.array([])
        self.bin_edges = np.array([])
        
        self.gain = np.nan
        self.gain_err = np.nan
        
        self.integral_window = None
        
        self.GainProcessor = None
        
        # def set_spe_fit(spe_fit):
        #     self.spe_fit
        self.spe_fit = None
        self.EventProcessor = None
    
class FastProcessor:
    def __init__(self,
                 data_folder: str, # path to the data folder 
                 list_of_files: list, 
                 ignore_channel_list = np.array([]),
                 calibration_run = False):

        self.data_folder = data_folder
        self.list_of_files = list_of_files
        self.ignore_channel_list = ignore_channel_list
        self.calibration_run = calibration_run
        
        # tmp_fast_info = FastInfo()
        # self.df = pd.DataFrame(columns = tmp_fast_info.__dict__.keys())
        
        self.list_of_fast_info = None
        
        # plot settings
        self.fontsize = "small"  
        
        # other settings that are shared by other programmes
        # self.share_config = rsc.configurations()
        
    def process_runs(self, n_random_WF = 100):
        if(len(self.list_of_files))==1:
            self.list_of_fast_info = self.process_run_single_run(self.list_of_files[0], 
                                                                 n_random_WF = n_random_WF)
            # otherwise it will loop over the single file path
            # e.g. "/", "h", "o", "m", "e", ...
        else:
            self.list_of_fast_info = self._v_process_run_single_run(self, self.list_of_files, 
                                                                    n_random_WF = n_random_WF)
        return
    
    def process_run_single_run(self, md_full_path: str, n_random_WF = 100):
        
        fast_info = FastInfo()
        GainProcessor = gain_processor.GainProcessor()
        RunProcessor = run_processor.RunProcessor()
        
        RunProcessor.update_info_from_metafile(md_full_path)
        fast_info.set_run_info_from_dict(RunProcessor.info.__dict__)        
        
        bin_full_path = RunProcessor.info.bin_full_path
        number_of_events = RunProcessor.info.number_of_events
        record_length_sample = RunProcessor.info.record_length_sample
        voltage_preamp1_V = RunProcessor.info.voltage_preamp1_V
        
        
        fast_info.gain, fast_info.gain_err = GainProcessor.process_single_run(bin_full_path,
                                               number_of_events,
                                               record_length_sample,
                                               voltage_preamp1_V,
                                               set_waveform=True)
        
        if GainProcessor.EventProcessor != None:
            
            fast_info.GainProcessor = GainProcessor
            fast_info.EventProcessor = GainProcessor.EventProcessor
            
            fast_info.integral_window = GainProcessor.EventProcessor.integral_window
            
            fast_info.areas = GainProcessor.areas
            fast_info.heights = GainProcessor.heights
        
            fast_info.randomly_selected_raw_WF = GainProcessor.EventProcessor.get_randomly_selected_WF(n_random_WF)[0]
            fast_info.randomly_selected_filtered_WF = GainProcessor.EventProcessor.get_randomly_selected_WF(n_random_WF)[1]
        
            fast_info.hist_count = GainProcessor.hist_count
            fast_info.bin_edges = GainProcessor.bin_edges
            
            # fast_info.baseline_n_samples = GainProcessor.EventProcessor.baseline_n_samples
            # fast_info.baseline_n_samples_avg = GainProcessor.EventProcessor.baseline_n_samples_avg
            # fast_info.n_channels = GainProcessor.EventProcessor.n_channels
            
            fast_info.baseline_std = GainProcessor.EventProcessor.baseline_std
            fast_info.baseline_mean = GainProcessor.EventProcessor.baseline_mean
            # fast_info.n_processed_events = GainProcessor.EventProcessor.n_processed_events
            # fast_info.start_index = GainProcessor.EventProcessor.start_index
        
        if GainProcessor.spe_fit != None:
            fast_info.spe_fit = GainProcessor.spe_fit
            
        # self.df.loc[len(self.df)] = fast_info.__dict__

        return fast_info

    _v_process_run_single_run = np.vectorize(process_run_single_run, excluded=["n_random_WF"], otypes=[np.ndarray])
     
    def plot_waveforms(self, show_plot = False, save_plot = False, channels = []):
        if isinstance(self.list_of_fast_info, list) or isinstance(self.list_of_fast_info, np.ndarray):
            if(len(self.list_of_fast_info) == 0):
                print("No data to plot. Run process_run first.")
                return  

            for fast_info in self.list_of_fast_info:
                if len(channels) != 0 and (fast_info.channel in channels):
                    logger.info(f"Skipping channel {fast_info.channels}")
                    continue
                else:
                    logger.info(f"Plotting for channel {fast_info.channel}")
                    self.plot_waveform_single_run(data = fast_info, 
                                                show_plot = show_plot, 
                                                save_plot = save_plot)
    
        elif isinstance(self.list_of_fast_info, FastInfo):
            fast_info = self.list_of_fast_info
            logger.info(f"Plotting for channel {fast_info.channel}")
            self.plot_waveform_single_run(data = fast_info, 
                                        show_plot = show_plot, 
                                        save_plot = save_plot)
            
        return
    
    def plot_waveform_single_run(self, data, show_plot = False, save_plot = True):

        if not show_plot and not save_plot:
            raise ValueError("Cannot have both show_plot and save_plot as False")

        threshold_mv = util.adc_to_mv(int(data.threshold_adc))
        # set the threshold to be 2 * Vpp
        optimal_threshold_mv =  (data.baseline_mean + 2 * (2 * np.sqrt(2) * data.baseline_std)) * 1000
        optimal_threshold_3sig_mv =  (data.baseline_mean + 3 * data.baseline_std) * 1000
        optimal_threshold_adc = util.mv_to_adc(optimal_threshold_mv)

        figure, axes = plt.subplots(3,2,figsize=(15,15))
        # figure.subplots_adjust(wspace=0.5)
        figure.subplots_adjust(hspace=0.3)
        time = np.arange(0, data.record_length_sample, 1) * 4

        randomly_selected_raw_WF = np.transpose(data.randomly_selected_raw_WF)
        randomly_selected_filtered_WF = np.transpose(data.randomly_selected_filtered_WF)
        
        axes[0,0].plot(time, 1000 * randomly_selected_raw_WF,color="red",alpha=0.2)
        axes[1,0].plot(time, 1000 * randomly_selected_raw_WF,color="red",alpha=0.2)
        axes[0,1].plot(time, 1000 * randomly_selected_filtered_WF,color="red",alpha=0.2)
        axes[1,1].plot(time, 1000 * randomly_selected_filtered_WF,color="red",alpha=0.2)
        
        axes[0,0].axhline(optimal_threshold_mv, linestyle = '--', color='g',label=f"Optimal threshold: \n{int(optimal_threshold_adc)}[ADC] \n{int(optimal_threshold_mv)}[mV]")
        axes[0,0].axhline(optimal_threshold_3sig_mv, linestyle = '-.', color='g',label=f"3 sig threshold: \n{int(optimal_threshold_3sig_mv)}[mV]")
        axes[0,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(data.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[0,0].set_xlim(0,time[-1]-100)

        point_in_middle = time[int(len(time)/2)]
        axes[1,0].axhline(optimal_threshold_mv, linestyle = '--', color='g')
        axes[1,0].text(point_in_middle, optimal_threshold_mv, '~5 sigma', ha ='center', va ='center') 
        axes[1,0].axhline(optimal_threshold_3sig_mv, linestyle = '-.', color='g')
        axes[1,0].text(point_in_middle, optimal_threshold_3sig_mv, '3 sigma', ha ='center', va ='center') 
        axes[1,0].axhline(threshold_mv, color='b',label=f"Test threshold: \n{int(data.threshold_adc)}[ADC] \n{int(threshold_mv)}[mV]", zorder=10)
        axes[1,0].set_xlim(0,time[-1]-100)

        _ymax = 1800
        axes[0,0].set_ylim(200,_ymax)
        axes[0,0].text(100,optimal_threshold_mv + _ymax/5,f"baseline mean: {1000 * data.baseline_mean:.1f} mV")
        axes[0,0].text(100,optimal_threshold_mv + _ymax/10,f"baseline std: {1000 * data.baseline_std:.2f} mV")
        axes[0,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,0].set_xlabel("Time [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[0,0].fill_betweenx([200,_ymax], data.integral_window[0]*np.max(time), data.integral_window[1]*np.max(time), color='gray', alpha=0.5)

        axes[0,1].set_xlim(0,time[-1]-100)
        axes[0,1].set_ylim(-5,1600)
        axes[0,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[0,1].set_xlabel("Time [ns]",fontsize=self.fontsize)
        
        _ymax = 350
        axes[1,0].set_xlim(0,time[-1]-100)
        axes[1,0].set_ylim(200,_ymax)
        axes[1,0].text(100,optimal_threshold_mv + _ymax/20,f"baseline mean: {1000 * data.baseline_mean:.1f} mV")
        axes[1,0].text(100,optimal_threshold_mv + _ymax/40,f"baseline std: {1000 * data.baseline_std:.2f} mV")
        axes[1,0].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,0].set_xlabel("Time [ns]",fontsize=self.fontsize)
        # plot intergral window
        axes[1,0].fill_betweenx([200,_ymax], data.integral_window[0]*np.max(time), data.integral_window[1]*np.max(time), color='gray', alpha=0.5)
        axes[1,0].axhline(1000 * data.baseline_mean, color="gray",linestyle="dashed",label=f"Baseline mean", zorder=10)

        _ymax = 40
        axes[1,1].set_xlim(0,time[-1]-100)
        axes[1,1].set_ylim(-5,_ymax)
        axes[1,1].set_ylabel("Voltage [mV]",fontsize=self.fontsize)
        axes[1,1].set_xlabel("Time [ns]",fontsize=self.fontsize)


        axes[2,0].hist(data.areas,
                        bins=data.GainProcessor.hist_n_bins,
                        range=data.GainProcessor.hist_range,
                        histtype='step',
                        color='red', 
                        label="Integrated area")
        axes[2,0].set_yscale("log")
        axes[2,0].set_ylabel("Count",fontsize=self.fontsize)
        axes[2,0].set_xlabel("Integrated Area [$V\cdot ns$]",fontsize=self.fontsize)
        axes[2,0].set_ylim(1e-1,None)

        if not self.calibration_run:
            # try:
            # spe_fit = FitSPE.FitSPE(data.bias_voltage, hist_count, bin_edges, plot = False, show_plot=False, save_plot=False)
            if (data.spe_fit != None):
                
                # mark found peaks
                axes[2,0].scatter(data.spe_fit.PE_rough_position, data.spe_fit.PE_rough_amplitude)
                
            if (data.spe_fit != None) and len(data.spe_fit.mu_list) > 0:
                # mark good peaks
                axes[2,0].plot(np.transpose(data.spe_fit.line_x[data.spe_fit.good_peaks]),
                               np.transpose(data.spe_fit.line_y[data.spe_fit.good_peaks]),
                               color='black')
                # mark bad peaks
                axes[2,0].plot(np.transpose(data.spe_fit.line_x[~data.spe_fit.good_peaks]),
                               np.transpose(data.spe_fit.line_y[~data.spe_fit.good_peaks]),
                               color='blue')
                
                if not (np.isnan(data.spe_fit.spe_position) or np.isnan(data.spe_fit.spe_position_error)):
                    
                    axes[2,0].axvline(data.spe_fit.spe_position, color="tab:green", label=f"Gain: {data.spe_fit.gain}")
                    axes[2,0].axvspan(data.spe_fit.spe_position - data.spe_fit.spe_position_error, data.spe_fit.spe_position + data.spe_fit.spe_position_error,
                                    alpha = 0.5, color="tab:green")
                
            # except:
            #     print("Could not fit SPE")

            handles, labels = axes[2,0].get_legend_handles_labels()
            custom_lines = [Line2D([0], [0], color='black'),
                            Line2D([0], [0], color='blue')]

            handles += custom_lines
            labels += ['Good fit','Bad fit']


        # axes[1,1].hist(heights,bins=100,range=(0,40),histtype='step')
        axes[2,1].hist2d(data.areas,data.heights,
                         bins=[data.GainProcessor.hist_n_bins,100],
                         range=[list(data.GainProcessor.hist_range),[0,60]],
                         cmap='viridis',
                         norm=LogNorm())
        # axes[2,1].hist2d(data.areas,data.heights,bins=[200,100],cmap='viridis',norm="log",label="")
        axes[2,1].set_ylabel("Filtered Height [mV]",fontsize=self.fontsize)
        axes[2,1].set_xlabel("Filtered integrated area [$V\cdot ns$]",fontsize=self.fontsize)
        

        for ax in axes.flatten():
            if ax == axes[2,0]:
                # Update legend with custom lines and labels
                ax.legend(handles=handles, labels=labels,loc='upper right')
            else:
                ax.legend()
        axes[0,0].set_title(f"Raw WFs channel {data.channel}")
        axes[0,1].set_title(f"Filtered WFs channel {data.channel}")
        axes[1,0].set_title(f"Zoomed raw WFs channel {data.channel}")
        axes[1,1].set_title(f"Zoomed filtered WFs channel {data.channel}")
        axes[2,0].set_title(f"Integrated area distribution channel {data.channel}")
        axes[2,1].set_title(f"Integrated area vs height channel {data.channel}")

        figure_path = os.path.join(self.data_folder,"plot/")
        if not os.path.exists(figure_path):
                os.makedirs(figure_path)

        plt.legend(self.fontsize)
        if save_plot:
            plt.savefig(os.path.join(figure_path,f"plot_{data.channel}.png"))
        
        if not show_plot:
            plt.close()

        return
    
    # def get_SPE(self, show_plot = False, save_plot = False, channels = []):
    #     if(len(self.df) == 0):
    #         print("No data to plot. Run process_run first.")
    #         return

    #     if len(channels) != 0:
    #         # select only the channels in the list
    #         mask = self.df['channel'].isin(channels)
    #         df = self.df.loc[mask]
    #     else:
    #         df = self.df

    #     spe_fit_list = []
    #     for i in range(len(df)):
    #         single_row_data = df.iloc[i]

    #         hist_count= np.array(single_row_data.hist_count)
    #         bin_edges = np.array(single_row_data.bin_edges)
    #         # try:
    #         spe_fit = FitSPE.FitSPE(hist_count, bin_edges, show_plot=show_plot, save_plot=save_plot)
    #         spe_fit_list.append(spe_fit)
    #         # except:
    #         #     print("Could not fit SPE")
            
    #     return spe_fit_list
    
    
if __name__ == "__main__":
    # meta_data_list = "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/20240624_T100_46V_3.0sig/config_23_2384_20240624_203027_board_1.bin"
    # data_folder = os.path.dirname(meta_data_list)
    # ignore_channel_list = ([])
    # calibration_run = False
    
    path = "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/20240624_T100_46V_4.0sig/"
    calibration_run = False # True if you want to check the calibration, False otherwise
    ignore_channel_list = np.array([])

    # ##########################
    # Load the meta data files
    if calibration_run:
        data_folder = os.path.join(path,"threshold_calibration/")
    else:
        data_folder = path

    meta_data_list = glob.glob(f"{data_folder}/*meta*")
    #reorganize the order of the meta_data_list, so the final one should be the newest one.

    # Sort the file paths based on the extracted date and time in ascending order (oldest to newest)
    new_meta_data_list = sorted(meta_data_list, key=util.extract_date_meta_data)
    new_meta_data_list = sorted(new_meta_data_list[-24:], key=util.extract_channel_meta_data)
    meta_data_list = new_meta_data_list[-24:]
    meta_data_list  
    
    test = FastProcessor(data_folder, meta_data_list, 
            ignore_channel_list=ignore_channel_list,
            calibration_run=calibration_run)
    test.process_runs()
    
    test.plot_waveforms(save_plot = False, show_plot=True)
    
        


        
