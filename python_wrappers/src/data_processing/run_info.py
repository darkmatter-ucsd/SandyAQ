from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class RunInfo:
    '''
    Dataclass to store the information of a single data file for run_processor.py.
    All attributes in this class corresponse to the columns of the output csv file
    If the number of columns is changed, run_processor.py will reprocess all runs 
    that were being processed.
    '''
    bin_full_path: str = ""
    md_full_path: str = ""
    
    date_time: pd.Timestamp = np.nan
    # run_tag: list = field(default_factory=list)
    run_tag: str = ""
    comment: str = ""
    
    n_channels: int = np.nan
    channel: int = np.nan
    board: int = np.nan
    threshold_adc: int = np.nan

    runtime_s: float = np.nan
    voltage_preamp1_V: float = np.nan
    temperature_K: float = np.nan
    
    number_of_events: int = np.nan
    n_processed_events: int = np.nan
    start_index: int = np.nan
    
    record_length_sample: int = np.nan
    baseline_n_samples: int = np.nan
    baseline_n_samples_avg: int = np.nan
    baseline_std: float = np.nan
    baseline_mean: float = np.nan
    
    # run_id is assigned after processing all data and sorted by date_time
    # see run_processor.process_runs()
    run_id: int = np.nan 
