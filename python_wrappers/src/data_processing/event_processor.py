import sys
import numpy as np
import os
import json

sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import data_processing.run_info as run_info
import data_processing.waveform_processor as waveform_processor
import common.config_reader as common_config_reader
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])


class EventProcessor:
    def __init__(self, run_info: run_info.RunInfo):
        
        self.failure_flag = False
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.info = run_info
        
        self.truncate_event_front = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "truncate_event_front")) #index to truncate the events before
        self.truncate_event_back = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "truncate_event_back")) #index to truncate the events before
        self.file_dir = os.path.dirname(self.info.bin_full_path)
        
        self.baseline_n_samples = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "n_baseline_samples")) #index to truncate the events before
        self.baseline_n_samples_avg = int(self.config.get("EVENT_PROCESSOR_SETTINGS", "n_baseline_samples_avg")) #index to truncate the events before
        
        tmp = self.config.get("EVENT_PROCESSOR_SETTINGS", "integral_window_for_area")
        tmp = tmp.split(' ')
        self.integral_window = (float(tmp[0]),float(tmp[1]))
        
        processing_mode = self.config.get("EVENT_PROCESSOR_SETTINGS", "mode")
        if processing_mode == "single_channel":
            self.n_channels = 1
        elif processing_mode == "all_channels":
            self.n_channels = 24
        else:
            try:
                processing_mode = int(processing_mode)
            except:
                raise Exception
            else:
                if processing_mode > 24 or processing_mode < 0:
                    raise ValueError("In the configuration file, " + \
                                     "processing_mode should be the number of" + \
                                     "channels, i.e. betweem 0 and 24")
                else:
                    self.n_channels = processing_mode
        
        self.process_all_events()
        
    def process_all_events(self) -> None:
        
        process_config = {"nchs": int(self.n_channels),
        "nsamps": int(self.info.record_length_sample),
        "sample_selection": int(self.baseline_n_samples), 
        "samples_to_average": int(self.baseline_n_samples_avg)}

        # dump the config to a json file
        sandpro_process_config_fname = self.common_cfg_reader.get_sandpro_process_config_path()
        with open(sandpro_process_config_fname, "w") as f:
            json.dump(process_config, f, indent=4)
        
        if (self.info.number_of_events > (self.truncate_event_front + self.truncate_event_back)):
                
            start_index, end_index = self.truncate_event_front, self.info.number_of_events - self.truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty

            processor= sandpro.processing.rawdata.RawData(config_file = sandpro_process_config_fname,
                                                    perchannel=False) # what does this perchannel mean?

            try:
                waveform = processor.get_rawdata_numpy(n_evts=self.info.number_of_events-1,
                                            file=self.info.bin_full_path, # specific .bin file
                                            bit_of_daq=14,
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
                    return
                    
            except Exception as e:
                logger.error("Error in reading the waveform for file: ", self.info.bin_full_path)
                self.failure_flag = True
                raise
            
            else:
                wfp = waveform_processor.WFProcessor(self.file_dir, volt_per_adc=2/2**14)
                wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
                wfp.process_wfs()
                
                self.baseline_std = np.mean(wfp.baseline_rms)
                self.baseline_mean = np.mean(wfp.baseline)
                self.n_processed_events = int(len(wfp.baseline_rms))
                self.start_index = int(start_index)
                
                self.areas = wfp.get_area(sum_window=self.integral_window)
                self.heights = wfp.get_height(search_window=self.integral_window)
                
                return
                
        else:
            logger.warning("Number of events not enough for analysis. \n" + \
                           "Abort with failure_flag ON.")
            
            self.failure_flag = True
            return
            
                
        