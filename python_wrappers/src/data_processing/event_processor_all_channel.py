import sys
import numpy as np
import os
import json

# sys.path.insert(0,"/home/daqtest/Processor/sandpro")
# import sandpro

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.run_info as run_info
import data_processing.waveform_processor as waveform_processor
import common.config_reader as common_config_reader
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])


class EventProcessor:
    def __init__(self, 
                 run_info: run_info.RunInfo,
                 bin_full_path: str,
                 n_channels):
        
        """
        Args:
            run_info (RunInfo): RunInfo object containing the information of the run
            n_channels:           number of channels, which is the
                                  number of channels in the DAQ board used

        Raises:
            Exception: if processing_mode is neither the required string
                       or a integer
            ValueError: if processing_mode is integer, need to be <24 or >=0
        """

        self.info = run_info
        self.info.bin_full_path = bin_full_path
        self.info.n_channels = n_channels

        ### check parameters
        if not os.path.exists(self.info.bin_full_path):
            raise FileNotFoundError(f"File not found: {self.info.bin_full_path}")
        if not isinstance(self.info.number_of_events, int) or self.info.number_of_events <= 0:        
            raise ValueError(f"number_of_events should be a positive integer, got {self.info.number_of_events}")
        if not isinstance(self.info.record_length_sample, int) or self.info.record_length_sample <= 0:
            raise ValueError(f"record_length_sample should be a positive integer, got {self.info.record_length_sample}")
        if self.info.data_taking_mode not in ["single_channel", "all_channels"]:
            raise ValueError(f"data_taking_mode should be either 'single_channel' or 'all_channels', got {self.info.data_taking_mode}")
        if not isinstance(n_channels, int) or n_channels <= 0 or n_channels > 32:
            raise ValueError(f"n_channels should be a positive integer, got {n_channels}")
        if not isinstance(self.info.post_trigger, float) or self.info.post_trigger < 0 or self.info.post_trigger > 100:
            raise ValueError(f"post_trigger should be a float between 0 and 100, got {self.info.post_trigger}")

        self.failure_flag = False
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.truncate_event_front = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "truncate_event_front")) #index to truncate the events before
        self.truncate_event_back = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "truncate_event_back")) #index to truncate the events before
        self.start_index, self.end_index = self.truncate_event_front, self.info.number_of_events - self.truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty
        
        self.file_dir = os.path.dirname(self.info.bin_full_path)
        
        self.baseline_n_samples = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "n_baseline_samples")) #index to truncate the events before
        self.baseline_n_samples_avg = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "n_baseline_samples_avg")) #index to truncate the events before

        self.hist_n_bins = int(self.config.get('GAIN_PROCESSOR_SETTINGS', 'hist_n_bins'))
        
        tmp = self.config.get("GAIN_PROCESSOR_SETTINGS", "hist_range")
        tmp = tmp.split(' ')
        self.hist_range = (float(tmp[0]),float(tmp[1]))
        
        # get integral window to compute area
        # tmp = self.config.get("EVENT_PROCESSOR_SETTINGS", "integral_window_for_area")
        # tmp = tmp.split(' ')
        # self.integral_window = (float(tmp[0]),float(tmp[1]))
        tmp_start = 1-self.info.post_trigger/100.0-0.1 # 0.1 is to avoid the edge effect
        self.integral_window = (tmp_start, tmp_start+0.25)
        
        self.data_taking_config = self.common_cfg_reader.get_data_taking_config()
        
        DAQ = self.data_taking_config.get("DAQ_MODULE", "DAQ") # which DAQ board
        
        self.n_bits = int(self.data_taking_config.get(DAQ, "n_bits"))
        range = float(self.data_taking_config.get(DAQ, "range"))
        
        self.volt_per_adc = range/float(2**self.n_bits)

        ### Results
        
        self.randomly_selected_raw_WF_V_list = []
        self.randomly_selected_filtered_WF_list = []

        self.set_sandro_config_path()
        self.waveform = self.get_waveforms()
        self.selected_waveform = None
        
        # self.process_all_events()

        
    
    
    def set_sandro_config_path(self) -> None:
        process_config = {"nchs": int(self.info.n_channels),
        "nsamps": int(self.info.record_length_sample),
        "sample_selection": int(self.baseline_n_samples), 
        "samples_to_average": int(self.baseline_n_samples_avg)}

        # dump the config to a json file
        sandpro_process_config_fname = self.common_cfg_reader.get_sandpro_process_config_path()
        with open(sandpro_process_config_fname, "w") as f:
            json.dump(process_config, f, indent=4)
            
        self.sandpro_process_config_fname = sandpro_process_config_fname
        return 
    
    def get_waveforms(self):

        path_config = self.common_cfg_reader.get_absolute_path_config()
        sandpro_path = path_config.get("PROCESSING_TOOL", "sandpro_dir")
        sys.path.insert(0,sandpro_path)
        import sandpro
        
        processor= sandpro.processing.rawdata.RawData(config_file = self.sandpro_process_config_fname,
        perchannel=False) # what does this perchannel mean?

        try:
            waveform = processor.get_rawdata_numpy(n_evts=self.info.number_of_events-1,
                    file=self.info.bin_full_path, # specific .bin file
                    bit_of_daq=self.n_bits,
                    headersize=4,inversion=False)
        except ValueError as e:
            self.failure_flag = True
            
            # passing only the broacast error, which is probably because the data_taking was
            # terminated earlier without correctly removing the files, resulting a difference
            # between set n_evts and actual n_evts. See below for how this works.
            # https://stackoverflow.com/questions/13531247/python-catching-specific-exception
            test_str = "could not broadcast input array from shape"
            if test_str not in str(e.args[0]): # check if test_str is in the error message
                raise # raise if not
            else:
                logger.warning(f"{e}\n\t set n_evts and actual n_evts probably does not match." + \
                                "Abort with failure_flag ON.")
                return None
                
        except Exception as e:
            logger.error("Error in reading the waveform for file: ", self.info.bin_full_path)
            self.failure_flag = True
            raise
        
        else:
            return waveform
        
        
    def process_all_events(self, channel: int) -> None:
        """_summary_

        Args:
            channel (int): channel number to process the events

        Returns:
            _type_: _description_
        """
        
        
        if (self.info.number_of_events > (self.truncate_event_front + self.truncate_event_back)):
                
            # waveform = self.get_waveforms()
            
            if type(self.waveform) is np.ndarray:
                
                wfp = waveform_processor.WFProcessor(self.file_dir, 
                        length_per_event = self.info.record_length_sample,
                        volt_per_adc=self.volt_per_adc)
                
                data_processed = self.waveform["data_per_channel"][self.start_index:self.end_index,channel,:]# in mV
                self.event_time_s = self.waveform['microseconds'][self.start_index:self.end_index]/1e6
                
                wfp.set_data(data_processed, unit="mV")
                wfp.process_wfs()
                
                self.info.baseline_std_V = np.mean(wfp.baseline_std_V)
                self.info.baseline_mean_V = np.mean(wfp.baseline_mean_V)
                self.info.n_processed_events = int(len(wfp.baseline_std_V))
                
                self.areas_Vns = wfp.get_area(sum_window=self.integral_window)
                self.heights_V = wfp.get_height(search_window=self.integral_window)
                self.rise_time_ns = wfp.get_rise_time_ns(search_window=self.integral_window)

                self.info.area_hist_count_Vns,self.info.area_bin_edges_Vns = np.histogram(
                    self.areas_Vns,
                    bins=self.hist_n_bins,
                    range=self.hist_range)


                self.processed_event_id = np.arange(0, self.info.n_processed_events)
                self.wfp = wfp


                # if set_waveform:
                #     self.waveform = waveform
                #     self.wfp = wfp
                # else:
                #     self.waveform = None
                #     self.wfp = None
                    
            else:
                self.failure_flag = True
                raise ValueError("Waveform data is empty. ")
                
        else:
            logger.warning("Number of events not enough for analysis. \n" + \
                           "Abort with failure_flag ON.")
            
            self.failure_flag = True
        
        return
            
                
    def get_randomly_selected_WF(
            self, 
            channel: int, 
            n_selection: int):
        """_summary_

        Args:
            channel (int): channel number to select the waveforms from
            n_selection (int): number of waveforms to be select

        Returns:
            if waveforms are saved
            tuple(array, array): randomly_selected_raw_WF_V, randomly_selected_filtered_WF
        """
        
        if type(self.waveform) is np.ndarray:
            data_processed = self.waveform["data_per_channel"][self.start_index:self.end_index,channel,:]# in mV
            
            # draw random row
            selected_rows_id = np.random.choice(
                self.processed_event_id, 
                size=n_selection, 
                replace=False)
            # this is done, instead of using np.random.randint
            # is because np.random.randint do not have replace option
            
            randomly_selected_raw_WF_V = data_processed[selected_rows_id,:]
            randomly_selected_filtered_WF_list = self.wfp.filtered_wfs[selected_rows_id,:]
            
            return randomly_selected_raw_WF_V, randomly_selected_filtered_WF_list
        
        else:
            logger.warning("self.waveform is None. \n" + \
                            "In case you ran: \n" + \
                            "this_class.process_all_events(),\n" + \
                            "you should have run: \n" + \
                            "this_class.process_all_events(set_waveform = True) \n" + \
                            "instead.")
            return
                   
    