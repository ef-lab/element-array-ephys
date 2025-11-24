## Imports
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import os
# import numcodecs
import datajoint as dj

## Database specifics
experiment_dir = '/mnt/lab/data01/OpenEphys'
db_prefix = 'lab_npx_'

dj.config['database.host'] = 'database.eflab.org:3306'
dj.config["enable_python_native_blobs"] = True
dj.config['custom'] = {'database_prefix': db_prefix,'ephys_root_data_dir': experiment_dir}


from build_pipeline import Subject, Session, Recording, probe, ephys, ephys_report

def get_key():
    while True:
        # Get user inputs
        animal_id = input("Enter animal_id: ").strip()
        session = input("Enter session: ").strip()
        insertion_number = input("Enter insertion number: ").strip()
    
        # Print and confirm
        print("\nYou entered:")
        print(f"  animal_id     : {animal_id}")
        print(f"  session       : {session}")
        print(f"  insertion number       : {insertion_number}")
        confirm = input("Are these the correct inputs? (yes/no): ").strip().lower()

    
        # safety check to confirm the inputs 
        if confirm == "yes":
            break
        else:
            print("Let's try again...\n")

        # Pick Probe
        print("\nNow let's choose a probe:")
        print(probe.Probe())
        probes = probe.Probe.fetch(format="frame")
        print(probes)
        probe_idx = input("pick the index of your choice")
        print(probe.iloc(3))

    key = {'animal_id' : int(animal_id), 'session': int(session), 'insertion_number' : int(insertion_number)}
    print(f'processing key: {key}')
    return key , probe_idx


def populate_ephys(key,probe_idx):
    ''' 
    A function that correctly checks and populates the Ephys schema with all its subsequent tables.
    '''

    
# TODO choose a different probe when they exist
    ephys.ProbeInsertion.insert1(
    dict(
        key,
        probe=(probe.Probe()).fetch('probe')[probe_idx],
        ), skip_duplicates=True
    )

    ephys.EphysRecording().populate(key, display_progress=True)



    key['paramset_idx']=3
    file_path = (ephys.EphysRecording.EphysFile() & key).fetch('file_path')
    ks_path = file_path[0]+'/kilosort4/sorter_output'
    ephys.ClusteringTask.insert1(
        dict(
            key,
            task_mode="load",  # load or trigger
            clustering_output_dir=ks_path,
        ), skip_duplicates=True
    )

    ephys.Clustering.populate(key, display_progress=True)
    ephys.CuratedClustering.populate(key, display_progress=True)
    ephys.QualityMetrics.populate(key, display_progress=True)
    



def main():
    key = get_key()
    print(f"Populating the Ephys schema for key:\n {key} ... ")
    populate_ephys(key)


if __name__ == "__main__":
    main()





