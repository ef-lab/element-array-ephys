## Imports
# import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import os
import numcodecs

import warnings
warnings.simplefilter("ignore")

import spikeinterface.full as si
# import probeinterface as pi
# from probeinterface.plotting import plot_probe

import datajoint as dj
dj.config['database.host'] = 'database.eflab.org:3306'

# exp = dj.create_virtual_module('experiments.py', 'lab_experiments')
# stim = dj.create_virtual_module('stimuli.py', 'lab_stimuli')
# beh = dj.create_virtual_module('behavior.py', 'lab_behavior')
rec = dj.create_virtual_module('recordings.py', 'lab_recordings')
# npx = dj.create_virtual_module('neuropixels.py', 'lab_neuropixels')

## Helpful functions
def replace_directory(a_directory):
    """
    Temporary Solution, use common.Paths.getLocal instead
    """
    # Define the mapping
    old_prefix1 = 'X:/OpenEphys\\'
    new_prefix1 = '/mnt/lab/data/OpenEphys/'

    old_prefix2 = 'W:/OpenEphys\\'
    new_prefix2 = '/mnt/lab/data01/OpenEphys/'

    old_prefix3 = 'W:/OpenEphys'
    new_prefix3 = '/mnt/lab/data01/OpenEphys/'

    # Replace the prefix
    if a_directory.startswith(old_prefix1):
        return a_directory.replace(old_prefix1, new_prefix1)
    elif a_directory.startswith(old_prefix2):
        return a_directory.replace(old_prefix2, new_prefix2)
    elif a_directory.startswith(old_prefix3):
        return a_directory.replace(old_prefix3, new_prefix3)
    else:
        print('Something is wrong with the OpenEphys path')


def get_session_directory(session_key: dict) -> str:
    """Retrieve the session directory with Neuropixels for the given session.

    Args:
        session_key (dict): A dictionary mapping subject to an entry in the subject table, and session_datetime corresponding to a session in the database.

    Returns:
        A string for the path to the session directory.
    """
    rep_dir = replace_directory((rec.Recording & session_key).fetch1("target_path"))
    print(rep_dir)
    if not rep_dir:
        raise ValueError(f"No path found for key: {session_key}")
    #print(rep_dir)
    
    return  rep_dir #session_dir/'Record Node 101/experiment1/recording1' 

        
def get_key():
    while True:
        # Get user inputs
        animal_id = input("Enter animal_id: ").strip()
        session = input("Enter session: ").strip()
    
        # Print and confirm
        print("\nYou entered:")
        print(f"  animal_id     : {animal_id}")
        print(f"  session       : {session}")
        confirm = input("Are these the correct inputs? (yes/no): ").strip().lower()
    
        # safety check to confirm the inputs 
        if confirm == "yes":
            break
        else:
            print("Let's try again...\n")

    key = {'animal_id' : int(animal_id), 'session': int(session)}
    print(f'processing key: {key}')
    return key


def process_session(key):
    # define number of cores for preprocessing:
    n_cpus = os.cpu_count()
    n_jobs = n_cpus - 4
    
    #set paths
    base_folder = Path(get_session_directory(key))
    openephys_folder = base_folder / 'Record Node 101'
    to_save_folder = openephys_folder / 'experiment1/recording1/continuous/Neuropix-PXI-100.ProbeA/'
    
    #load rec
    full_raw_rec = si.read_openephys(openephys_folder, load_sync_channel=False)
    # #and probe info
    # probe = full_raw_rec.get_probe()
    
    print('preprocessing..')
    if (to_save_folder / "preprocessed").is_dir():
        recording_saved = si.load_extractor(to_save_folder / "preprocessed")
    else: # do the preprocessing
        recording_to_process = full_raw_rec
        #filtering
        recording_f = si.bandpass_filter(recording_to_process, freq_min=300, freq_max=9000)
        recording_cmr = si.common_reference(recording_f, reference='global', operator='median')
        #remove bad channels
        bad_channel_ids, channel_labels = si.detect_bad_channels(recording_f, method='coherence+psd')
        recording_good_channels_f = recording_f.remove_channels(bad_channel_ids)
        recording_good_channels = si.common_reference(recording_good_channels_f, reference='global', operator='median')
        # and save
        job_kwargs = dict(n_jobs=n_jobs, chunk_duration="1s", progress_bar=True)
        recording_saved = recording_good_channels.save(folder=to_save_folder / "preprocessed", **job_kwargs)
    
    print('create compressed preprocessed..')
    if (to_save_folder / "preprocessed_compressed.zarr").is_dir():
        ## if compressed preprocessed exist:
        print('compressed preprocessed already saved')
        #recording_saved = si.read_zarr(to_save_folder / "preprocessed_compressed.zarr")
    else: #save 
        compressor = numcodecs.Blosc(cname="zstd", clevel=9, shuffle=numcodecs.Blosc.BITSHUFFLE)
        recording_saved = recording_good_channels.save(format="zarr", folder=to_save_folder / "preprocessed_compressed.zarr",
                                         compressor=compressor,
                                         **job_kwargs)
    
    ## run kilosort4 in container:
    # define params
    print('preparing to run kilosort..')

    # these params are for paramset_idx=3
    sorter_params = {"batch_size": 100000,
        "acg_threshold":0.1,
        "ccg_threshold":0.15,
        "duplicate_spike_ms": 0.15,
        "pool_engine": "process",
        "n_jobs": 1,
        "chunk_duration": "1s",
        "progress_bar": True,
        "mp_context": None,
        "max_threads_per_worker": 1,}
    
    if (to_save_folder / "kilosort4").is_dir():
        print('sorting already saved')
        sorting_KS4 = si.read_kilosort(to_save_folder / "kilosort4/sorter_output")
    else: 
        print('run spike sorting')
        # run spike sorting on entire recording
        sorting_KS4 = si.run_sorter('kilosort4', recording_saved, 
                                    output_folder=to_save_folder / 'kilosort4',
                                    verbose=True, docker_image=True, 
                                    **sorter_params)
        print(sorting_KS4)
    
        #remove empty units if any
        sorting_KS4 = sorting_KS4.remove_empty_units()
        print(f'KS4 found {len(sorting_KS4.get_unit_ids())} non-empty units')
    
    ## create a sorting analyzer
    if (to_save_folder / "sorting_analyzer").is_dir():
        print('analyzer already saved')
        analyzer = si.load_sorting_analyzer(
            folder=to_save_folder / "sorting_analyzer"
        )
    
        ## add: check that all metrics folders exist and 
        # print('metrics computed')
    else: 
        print('analyzer...')
        analyzer = si.create_sorting_analyzer(
            sorting=sorting_KS4,
            recording=recording_saved,
            folder=to_save_folder / "sorting_analyzer",
            format="binary_folder",
            sparse=True,
            overwrite=True
        )
    
        #compute stuff
        print('computing metrics..')
        analyzer.compute(["noise_levels", "random_spikes", "waveforms", "templates"])
        analyzer.compute(
            "spike_amplitudes",
            peak_sign="pos"
        )
        analyzer.compute(["unit_locations", "spike_locations", "correlograms", "principal_components"])
        analyzer.compute('template_metrics', include_multi_channel_metrics=True)
        
        #compute quality metrics
        dqm_params = si.get_default_qm_params()
        analyzer.compute(
            "quality_metrics",
            qm_params=dqm_params
        )
    
    ## all processing done
    print(f'processing done for {key}')


def main():
    key = get_key()
    process_session(key)


if __name__ == "__main__":
    main()

