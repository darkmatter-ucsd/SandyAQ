
import sandpro
import WaveformProcessor

import common.read_share_config as rsc



class PostProcessing:
    
    def __init__(self, file_path, sandpro_process_config_fname, ):
        self.share_config = rsc.configurations()
        
        processor= sandpro.processing.rawdata.RawData(config_file = sandpro_process_config_fname,
                                                perchannel=False) # what does this perchannel mean?

        start_index, end_index = truncate_event_front, info.number_of_events - truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty
        
        
        try:
            waveform = processor.get_rawdata_numpy(n_evts=info.number_of_events-1,
                                        file=info.file_path, # specific .bin file
                                        bit_of_daq=14,
                                        headersize=4,inversion=False)
            
            wfp = WaveformProcessor.WFProcessor(file_dir, volt_per_adc=2/2**14)
            wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
            wfp.process_wfs()
            
        except Exception as e:
            print(e)
            try:
                waveform = processor.get_rawdata_numpy(1999,
                                            file=info.file_path, # specific .bin file
                                            bit_of_daq=14,
                                            headersize=4,inversion=False)
                start_index, end_index = 1000, 1900 #first 1000 events are noisy

                wfp = WaveformProcessor.WFProcessor(file_dir, volt_per_adc=2/2**14)
                wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
                wfp.process_wfs()